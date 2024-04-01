"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""
import logging
import os
import tempfile
import time
from typing import Dict, List, Optional

import yaml

import buildrunner.docker
from buildrunner.config import BuildRunnerConfig
from buildrunner.config.models import GlobalSecurityScanConfig
from buildrunner.config.models_step import StepPushCommit, StepPushSecurityScanConfig
from buildrunner.docker.image_info import BuiltImageInfo
from buildrunner.docker.multiplatform_image_builder import MultiplatformImageBuilder
from buildrunner.docker.runner import DockerRunner
from buildrunner.errors import (
    BuildRunnerProcessingError,
)
from buildrunner.steprunner.tasks import BuildStepRunnerTask
from buildrunner.utils import sanitize_tag


LOGGER = logging.getLogger(__name__)
ARTIFACT_SECURITY_SCAN_KEY = "docker:security-scan"


class RepoDefinition:
    """
    Contains the definition for a push repository.
    """

    def __init__(
        self,
        repository: str,
        tags: Optional[List[str]],
        security_scan: Optional[StepPushSecurityScanConfig],
    ):
        self.security_scan = security_scan
        # Force a lower-case repo
        repo_lower = repository.lower()
        if repo_lower != repository:
            LOGGER.info(
                f"Forcing repository to lowercase: {repository} => {repo_lower}"
            )
        self.repository = repo_lower

        if tags:
            self.tags = [sanitize_tag(tag) for tag in tags]
        else:
            self.tags = []

        # if there is a tag in the repository value, strip it off and add the tag to the list of tags
        tag_index = self.repository.find(":")
        if tag_index > 0:
            tag = self.repository[tag_index + 1 :]
            if tag not in self.tags:
                self.tags.append(tag)
            self.repository = self.repository[0:tag_index]


class PushBuildStepRunnerTask(BuildStepRunnerTask):
    """
    Class used to push the resulting image (either from the build task, or if
    there is a run task, the snapshot of the resulting run container) to the
    given registry/repository.
    """

    def __init__(self, step_runner, pushes: List[StepPushCommit], commit_only=False):
        super().__init__(step_runner, pushes[0])
        self._docker_client = buildrunner.docker.new_client(
            timeout=step_runner.build_runner.docker_timeout,
        )
        self._commit_only = commit_only
        self._repos = [
            RepoDefinition(
                push.repository,
                push.tags,
                push.security_scan,
            )
            for push in pushes
        ]

    def _security_scan_mp(
        self,
        built_image: BuiltImageInfo,
        log_image_ref: str,
        push_security_scan: Optional[StepPushSecurityScanConfig],
    ) -> Dict[str, dict]:
        """
        Does a security scan for each built image in a multiplatform image.
        :param built_image: the multiplatform built image info
        :param log_image_ref: the image label to log
        :param push_security_scan: the optional security scan overrides
        :return: a dictionary of platform names to security scan information (for each built platform image)
        """
        scan_results = {}
        for image in built_image.built_images:
            result = self._security_scan(
                repository=image.repo,
                tag=image.tag,
                log_image_ref=f"{log_image_ref}:{image.platform}",
                pull=True,
                push_security_scan=push_security_scan,
            )
            if result:
                scan_results[image.platform] = result
        if not scan_results:
            return {}
        return {ARTIFACT_SECURITY_SCAN_KEY: scan_results}

    def _security_scan_single(
        self,
        repo: str,
        tag: str,
        push_security_scan: Optional[StepPushSecurityScanConfig],
    ) -> Dict[str, dict]:
        log_image_ref = f"{repo}:{tag}"
        result = self._security_scan(
            repository=repo,
            tag=tag,
            log_image_ref=log_image_ref,
            pull=False,
            push_security_scan=push_security_scan,
        )
        if not result:
            return {}
        return {
            ARTIFACT_SECURITY_SCAN_KEY: {
                MultiplatformImageBuilder.get_native_platform(): result
            }
        }

    def _security_scan(
        self,
        *,
        repository: str,
        tag: str,
        log_image_ref: str,
        pull: bool,
        push_security_scan: Optional[StepPushSecurityScanConfig],
    ) -> Optional[dict]:
        # If the security scan is not enabled, do nothing
        security_scan_config = BuildRunnerConfig.get_instance().global_config.security_scan.merge_scan_config(
            push_security_scan
        )
        if log_image_ref != f"{repository}:{tag}":
            log_image_ref = f"{log_image_ref} ({repository}:{tag})"
        if not security_scan_config.enabled:
            LOGGER.debug(
                f"Image scanning is disabled, skipping scan of {log_image_ref}"
            )
            return None

        LOGGER.info(
            f"Scanning {log_image_ref} for security issues using {security_scan_config.scanner}"
        )

        if security_scan_config.scanner == "trivy":
            return self._security_scan_trivy(
                security_scan_config=security_scan_config,
                repository=repository,
                tag=tag,
                log_image_ref=log_image_ref,
                pull=pull,
            )
        raise Exception(f"Unsupported scanner {security_scan_config.scanner}")

    @staticmethod
    def _security_scan_trivy_parse_results(
        security_scan_config: GlobalSecurityScanConfig, results: dict
    ) -> dict:
        max_score = 0
        vulnerabilities = []
        for result in results.get("Results", []):
            if not result.get("Vulnerabilities"):
                continue
            for cur_vuln in result.get("Vulnerabilities"):
                score = cur_vuln.get("CVSS", {}).get("nvd", {}).get("V3Score")
                vulnerabilities.append(
                    {
                        "cvss_v3_score": score,
                        "severity": cur_vuln.get("Severity"),
                        "vulnerability_id": cur_vuln.get("VulnerabilityID"),
                        "pkg_name": cur_vuln.get("PkgName"),
                        "installed_version": cur_vuln.get("InstalledVersion"),
                        "primary_url": cur_vuln.get("PrimaryURL"),
                    }
                )
                if score:
                    max_score = max(max_score, score)

        if security_scan_config.max_score_threshold:
            if max_score >= security_scan_config.max_score_threshold:
                raise BuildRunnerProcessingError(
                    f"Max vulnerability score ({max_score}) is above the "
                    f"configured threshold ({security_scan_config.max_score_threshold})"
                )
            LOGGER.info(
                f"Max vulnerability score ({max_score}) is less than the "
                f"configured threshold ({security_scan_config.max_score_threshold})"
            )
        else:
            LOGGER.debug(
                f"Max vulnerability score is {max_score}, but no max score threshold is configured"
            )
        return {
            "max_score": max_score,
            "vulnerabilities": vulnerabilities,
        }

    def _security_scan_trivy(
        self,
        *,
        security_scan_config: GlobalSecurityScanConfig,
        repository: str,
        tag: str,
        log_image_ref: str,
        pull: bool,
    ) -> dict:
        # Pull image for scanning (if not already pulled) so that it can be scanned locally
        if pull:
            self._docker_client.pull(repository, tag)

        buildrunner_config = BuildRunnerConfig.get_instance()
        with tempfile.TemporaryDirectory(
            suffix="-trivy-run",
            dir=buildrunner_config.global_config.temp_dir,
        ) as local_run_dir:
            # Set constants for this run
            config_file_name = "config.yaml"
            results_file_name = "results.json"
            container_run_dir = "/trivy"
            # Dynamically use the configured cache directory if set, uses the trivy default otherwise
            container_cache_dir = security_scan_config.config.get(
                "cache-dir", "/root/.cache/trivy"
            )

            # Create local directories for volume mounting (if they don't exist)
            local_cache_dir = security_scan_config.cache_dir
            if not local_cache_dir:
                local_cache_dir = os.path.join(
                    buildrunner_config.global_config.temp_dir, "trivy-cache"
                )
            os.makedirs(local_cache_dir, exist_ok=True)

            # Create run config
            with open(
                os.path.join(local_run_dir, config_file_name), "w", encoding="utf8"
            ) as fobj:
                yaml.safe_dump(security_scan_config.config, fobj)

            image_scanner = None
            try:
                image_config = DockerRunner.ImageConfig(
                    f"{BuildRunnerConfig.get_instance().global_config.docker_registry}/"
                    f"aquasec/trivy:{security_scan_config.version}",
                    pull_image=False,
                )
                image_scanner = DockerRunner(
                    image_config,
                    log=self.step_runner.log,
                )
                image_scanner.start(
                    entrypoint="/bin/sh",
                    volumes={
                        local_run_dir: container_run_dir,
                        local_cache_dir: container_cache_dir,
                        # TODO Implement support for additional connection methods
                        "/var/run/docker.sock": "/var/run/docker.sock",
                    },
                )

                # Print out the trivy version
                image_scanner.run("trivy --version", console=self.step_runner.log)

                # Run trivy
                start_time = time.time()
                exit_code = image_scanner.run(
                    f"trivy --config {container_run_dir}/{config_file_name} image "
                    f"-f json -o {container_run_dir}/{results_file_name} {repository}:{tag}",
                    console=self.step_runner.log,
                )
                LOGGER.info(
                    f"Took {round(time.time() - start_time, 1)} second(s) to scan image"
                )
                if exit_code:
                    raise BuildRunnerProcessingError(
                        f"Could not scan {log_image_ref} with trivy, see errors above"
                    )

                # Load results file and parse the max score
                results_file = os.path.join(local_run_dir, results_file_name)
                if not os.path.exists(results_file):
                    raise BuildRunnerProcessingError(
                        f"Results file {results_file} from trivy for {log_image_ref} does not exist, "
                        "check for errors above"
                    )
                with open(results_file, "r", encoding="utf8") as fobj:
                    results = yaml.safe_load(fobj)
                if not results:
                    raise BuildRunnerProcessingError(
                        f"Could not read results file {results_file} from trivy for {log_image_ref}, "
                        "check for errors above"
                    )
                return self._security_scan_trivy_parse_results(
                    security_scan_config, results
                )
            finally:
                if image_scanner:
                    # make sure the current user/group ids of our
                    # process are set as the owner of the files
                    exit_code = image_scanner.run(
                        f"chown -R {int(os.getuid())}:{int(os.getgid())} {container_run_dir}",
                        log=self.step_runner.log,
                    )
                    if exit_code != 0:
                        LOGGER.error("Error running trivy--unable to change ownership")
                    image_scanner.cleanup()

    def run(self, context):  # pylint: disable=too-many-branches
        # Tag multi-platform images
        built_image = context.get("mp_built_image")
        if built_image:
            # These are used in the image artifacts below, and should match for all tagged images
            built_image_ids_str = ",".join(
                [image.trunc_digest for image in built_image.built_images]
            )
            built_image_id_with_platforms = [
                f"{image.platform}:{image.trunc_digest}"
                for image in built_image.built_images
            ]

            for repo in self._repos:
                tagged_image = built_image.add_tagged_image(repo.repository, repo.tags)

                # Add tagged image refs to committed images for use in determining if pull should be true/false
                for image_ref in tagged_image.image_refs:
                    self.step_runner.build_runner.committed_images.add(image_ref)

                # Add tagged image as artifact if this is a push and not just a commit
                if not self._commit_only:
                    self.step_runner.build_runner.add_artifact(
                        repo.repository,
                        {
                            "type": "docker-image",
                            "docker:image": built_image_ids_str,
                            "docker:repository": repo.repository,
                            "docker:tags": repo.tags,
                            "docker:platforms": built_image_id_with_platforms,
                            **self._security_scan_mp(
                                built_image,
                                f"{repo.repository}:{repo.tags[0]}",
                                repo.security_scan,
                            ),
                        },
                    )

            # Tag all images locally for the native platform
            self.step_runner.multi_platform.tag_native_platform(built_image)

        # Tag single platform images
        else:
            # first see if a run task produced an image (via a post-build config)
            if "run-image" in context:
                image_to_use = context.get("run-image")
            # next see if there was a run task, committing the end state of the
            # container as the image to use
            elif "run_runner" in context:
                image_to_use = context["run_runner"].commit(self.step_runner.log)
            # finally see if we have an image from a build task
            else:
                image_to_use = context.get("image", None)

            # validate we have an image
            if not image_to_use:
                raise BuildRunnerProcessingError(
                    "Cannot find an image to tag/push from a previous task"
                )
            self.step_runner.log.write(f"Using image {image_to_use} for tagging\n")

            # add the image to the list of generated images for potential cleanup
            self.step_runner.build_runner.generated_images.append(image_to_use)

            for repo in self._repos:
                if self._commit_only:
                    self.step_runner.log.write(
                        f'Committing resulting image as "{repo.repository}" with tags {", ".join(repo.tags)}.\n'
                    )
                else:
                    self.step_runner.log.write(
                        f'Preparing resulting image for push to "{repo.repository}" with tags {", ".join(repo.tags)}.\n'
                    )

                # Tag the image
                for tag in repo.tags:
                    self._docker_client.tag(
                        image_to_use,
                        repo.repository,
                        tag=tag,
                        force=True,
                    )
                    self.step_runner.build_runner.committed_images.add(
                        f"{repo.repository}:{tag}"
                    )

                    if not self._commit_only:
                        self.step_runner.build_runner.repo_tags_to_push.append(
                            (
                                f"{repo.repository}:{tag}",
                                # Used to be insecure registry, but this is now deprecated/removed
                                False,
                            )
                        )

                # add image as artifact
                if not self._commit_only:
                    self.step_runner.build_runner.add_artifact(
                        os.path.join(self.step_runner.name, image_to_use),
                        {
                            "type": "docker-image",
                            "docker:image": image_to_use,
                            "docker:repository": repo.repository,
                            "docker:tags": repo.tags,
                            **self._security_scan_single(
                                repo.repository, repo.tags[-1], repo.security_scan
                            ),
                        },
                    )


class CommitBuildStepRunnerTask(PushBuildStepRunnerTask):
    """
    Class used to commit the resulting image (either from the build task, or if
    there is a run task, the snapshot of the resulting run container) with a
    tag matching the given registry/repository.
    """

    def __init__(self, step_runner, commits: List[StepPushCommit]):
        # Subclasses the push task, just set commit only to true
        super().__init__(step_runner, commits, commit_only=True)
