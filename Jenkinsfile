@Library('gauntlet') _

node('docker') {
    checkoutToLocalBranch()
    sh('python ./setup.py test')
    buildrunner()
}
