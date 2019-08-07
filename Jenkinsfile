@Library('gauntlet') _

node('docker') {
    stage("Test") {
        checkoutToLocalBranch()
        sh('python ./setup.py test')
    }
    stage("Build") {
        buildrunner()
    }
}
