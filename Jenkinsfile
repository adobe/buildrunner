@Library('gauntlet') _

node('docker') {
    // Get Jenkins user and group
    def user = sh(script: "id -u", returnStdout: true).trim()
    def group = sh(script: "id -g", returnStdout: true).trim()
    // Build the image and run commands in it
    def image = docker.build(null, '-f Dockerfile.build')
    image.inside("-v /var/run/docker.sock:/var/run/docker.sock -v ${pwd()}:/source ${envVarsString} -u root:root") {
	try {
            sh 'cd /source; python ./setup.py test'
	} finally {
            // At the end of the build, chown everything as the jenkins user/group so that we don't have permission errors
            sh("chown -R ${user}:${group} .")
	}
    }

    stage("Build") {
        buildrunner()
    }
}


