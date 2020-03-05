@Library('gauntlet') _

node('docker') {
    // Tests are initiated here because they need to run outside of
    // Docker in order to test creating and running Docker containers
    // (nested Docker does not work).
    stage("Test") {
        checkoutToLocalBranch()
        // Cleanup the buildrunner yaml from any previous runs (if it exists)
        sh('''
            set -eux;
            printf '
	       NOTE: This test suite cannot execute inside of Docker because
	             it invokes Docker (nested Docker does not work).
	             Consequently the execution space needs to have all
                     necessary Buildrunner dependencies installed or
                     Buildrunner or the tests will fail.
            ';
	    rm -f .buildrunner.yaml;
            python ./setup.py test;
        ''')
    }
    stage("Build") {
        buildrunner()
    }
}
