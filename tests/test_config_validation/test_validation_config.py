import pytest


@pytest.mark.parametrize(
    "config_data, error_matches",
    [
        #  Invalid version
        ({"version": "string"}, ["Input should be a valid number"]),
        #  Valid version
        ({"version": 2.0, "steps": {}}, []),
        # Optional version
        ({"steps": {}}, []),
        # Sample valid config, but not exhaustive
        (
            """
    version: 2.0
    steps:
      build-container-single-platform1:
        build:
          path: .
          dockerfile: Dockerfile
          pull: false
          platform: linux/amd64
        push:
          repository: mytest-reg/buildrunner-test
          tags:
            - latest
      build-container-multi-platform2:
        build:
          path: .
          dockerfile: Dockerfile
          pull: false
          platforms:
            - linux/amd64
            - linux/arm64
        push:
          repository: mytest-reg/buildrunner-test-multi-platform
          tags:
            - latest
      build-container-multi-platform-push3:
        build:
          path: .
          dockerfile: Dockerfile
          pull: false
          platforms:
            - linux/amd64
            - linux/arm64
        push:
          - myimages/image1
          - repository: myimages/image2
            tags:
              - latest
    """,
            [],
        ),
        # Multiple errors
        # Invalid to have version as a string
        # Invalid to have platforms and platform
        (
            """
    version: string
    steps:
      build-container-multi-platform:
        build:
          path: .
          dockerfile: Dockerfile
          pull: false
          platform: linux/amd64
          platforms:
            - linux/amd64
            - linux/arm64
        push:
          repository: mytest-reg/buildrunner-test-multi-platform
          tags:
            - latest
    """,
            ["Input should be a valid number", "Cannot specify both platform"],
        ),
        # Tests the documentation example with minimal changes to make valid yaml
        (
            """
    steps:
      generate_files:
        run:
          image: docker.company.com/abc-xdm-proto-build:latest
          ssh-keys: ["company-github"]
          env:
            GIT_TOKEN: 'blahblahblahblahblahblah'
          cmd: sbt clean generateAwareJsonFiles combineXDM generateProtobufFiles
          artifacts:
            'target/protobufFiles/Database*.proto':
            'target/rawJson/Database*.json':
            'target/AwareJson/Aware.json':
            'target/combinedXDM/complete-schema-template.schema.json':
      build-dev-rpm:
        build:
          inject:
            "buildrunner.results/generate_files/*.proto": "proto/"
            "buildrunner.results/generate_files/A*.json": "json/"
            "db_build/dms.repo.centos7": db_build/dms.repo
          dockerfile: |
            FROM docker-release.dr.corp.company.com/centos-7-x86_64-obuild:latest
            ADD db_build/dms.repo /etc/yum.repos.d/dms.repo
            RUN rpm --rebuilddb; yum clean all; yum install -y db-omniture-libs-protobuf-2.6.1 db-scds-proto-1.0 db-scds-json-1.0
            ADD proto/*.proto /tmp/proto/
            ADD json/*.json /tmp/json/
        run:
          cmds:
            - "chown -R httpd:www /source"
            - "echo ~ Compiling previous proto version..."
            - "mkdir -p /tmp/existingscds && for f in `ls -d /home/omniture/protobuf/scds/*.proto`; do protoc -I=/home/omniture/protobuf --cpp_out /tmp/existingscds $f; done"
            - "echo ~ Compiling current proto version..."
          artifacts:
            # pull the log if rpmbuild fails
            "db_tmp/rpm/TMPDIR/*.log": {type: 'log'}
            # pull the noarch packages
            "db_tmp/rpm/RPMS/noarch/*.noarch.rpm": {platform: 'centos-noarch'}
      build-proto-java:
        build:
          inject:
            "buildrunner.results/generate_files/*.proto": "proto"
          dockerfile: |
            FROM docker.company.com/abc-base-containers/protobuf-builder:java8-2.5.0
            ADD proto/*.proto /tmp/proto/scds/
        run:
          caches:
            maven: "/root/.m2/repository"
          cmds: [
            'mvn package ${BUILDRUNNER_DO_PUSH+deploy} -am -pl proto-java'
          ]
          artifacts:
            '*/target/*.jar':
      download-country:
        build:
          inject:
            "db_build/bin/*": "db_build/bin/"
          dockerfile: |
            FROM docker-release.dr.corp.company.com/centos-7-x86_64-obuild
            ADD db_build/bin/* /tmp/
        run:
          cmds:
            - '/tmp/download_country.sh'
            # strip all quotes
            - "sed -i 's/bogus//g' country_codes.csv"
            # Add missing ?,? because it's not in the DB
            - 'echo "?,?" >> country_codes.csv'
            # keep first 2 columns, uppercase 2nd column
            - 'awk -F, ''{OFS=","; $2 = toupper($2); {print $1,$2}}'' country_codes.csv > country_code_map.csv'
          artifacts:
            'country_code_map.csv':
      build-transform-proto-xdm:
        build:
          inject:
            "buildrunner.results/generate_files/*.proto": "proto"
            "buildrunner.results/generate_files/*.json": "json"
          dockerfile: |
            FROM docker.company.com/abc-base-containers/protobuf-builder:java8-2.5.0
            RUN apt-get update && apt-get -y install openssh-client
            ADD proto/*.proto /tmp/proto/scds/
        run:
          env:
            ARTIFACTORY_USER: 'cool_user'
            ARTIFACTORY_API_TOKEN: 'blahblahblahblahblahblahblah'
          caches:
            maven: "/root/.m2/repository"
          shell: /bin/bash
          cmds: [
            'cp /tmp/json/raw/*json json/raw',
            'mkdir -p csv',
            'cp /tmp/csv/*csv csv',
            'curl -L https://github.com/stedolan/jq/releases/download/jq-1.5/jq-linux64 > jq',
            'chmod +x jq',
          ]
          artifacts:
            'transform-proto-xdm/target/*':
            'transform-proto-xdm-generator/target/*':
            'validator-xdm/target/*':
      generate_docs:
        run:
          image: docker.company.com/abc-xdm-proto-build:latest
          ssh-keys: ["company-github"]
          env:
            GIT_TOKEN: 'blahblahblahblahblahblahblah'
          cmd: "sbt clean generateDocs ${BUILDRUNNER_DO_PUSH+publishGHPages}"
          artifacts:
            'target/docs/*':
    """,
            [],
        ),
        # Valid github config
        (
            """
    github:
      company_github:
        endpoint: 'https://git.company.com/api'
        version: 'v3'
        username: 'USERNAME'
        app_token: 'APP_TOKEN'
    """,
            [],
        ),
        # Invalid github config
        (
            """
    github:
      company_github:
        endpoint: 'https://git.company.com/api'
        version: 'v3'
        username: 'USERNAME'
        app_token: 'APP_TOKEN'
        bogus: 'bogus'
    """,
            ["Extra inputs are not permitted"],
        ),
    ],
)
def test_config_data(
    config_data, error_matches, assert_generate_and_validate_config_errors
):
    assert_generate_and_validate_config_errors(config_data, error_matches)
