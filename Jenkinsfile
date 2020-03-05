@Library('gauntlet') _

node('docker') {
    stage("Test") {
        checkoutToLocalBranch()
	// Install dependencies
        sh('yum -y install python-devel gcc')
        // Cleanup the buildrunner yaml from any previous runs (if it exists)
        sh('rm -f .buildrunner.yaml')
        sh('python ./setup.py test')
    }
    stage("Build") {
        buildrunner()
    }
}
