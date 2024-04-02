##############
 Installation
##############

There are two different options for installing Buildrunner.  Each option
depends on `Docker <http://www.docker.com/getdocker>`_.  Windows also depends
on ``BASH``, which can be found at `Git Bash <https://git-for-windows.github.io/>`_.

.. contents::
   :local:

Pip
###

If you wish to install buildrunner directly on your local machine, install via
pip. This is best done when installing into a virtual environment using virtualenv.
The following commands will create a new virtual environment, activate it, and
install Buildrunner within it:

.. code:: bash

  virtualenv buildrunner
  source buildrunner/bin/activate
  pip install buildrunner

The buildrunner executable is now available at buildrunner/bin/buildrunner and
can be added to your path.

.. tip::

    If you are getting 404 errors for authenticated registries but you can pull them with
    ``docker pull`` - messages similar to the following:

    docker.errors.NotFound: 404 Client Error: Not Found ("manifest for <image> not found: manifest
    unknown: The named manifest is not known to the registry.")

    then you likely need to downgrade the installed python docker library version with ``pip
    install docker==3.6.0``. Version 3.7.0 broke compatibility with buildrunner and docker credential
    helpers.

Docker Container
################

Buildrunner can be run as a Docker container.  This works cross-platform and
is the easiest way to keep up to date.

To install, simply clone the `buildrunner repository
<https://github.com/adobe/buildrunner>`_  and add the
``scripts`` directory to your ``$PATH``.  ``scripts`` contains wrapper scripts
that pass the appropriate context to the Docker container.  There is a `BASH
<https://github.com/adobe/buildrunner/blob/master/scripts/buildrunner>`__
script and a Windows `batch file
<https://github.com/adobe/buildrunner/blob/master/scripts/buildrunner.bat>`_,
which simply calls the ``BASH`` script.

.. note:: WINDOWS USERS: This is the recommended method for Windows users, however, you must make
   sure that you are using the `BASH shell
   <https://www.laptopmag.com/articles/use-bash-shell-windows-10>`_ enhancements for Windows or that
   you have something installed that enables the use of ``sh``, or else this method will not work.
   If you are using WSL and the hyper-v installation of docker:

   1. Click on the "Expose deamon on tcp://localhost:2375 without tls" from inside of the docker settings
   2. Use the pip install method inside of the WSL subsystem
   3. Export your docker host ``DOCKER_HOST=tcp://localhost:2375`` inside of WSL

.. note:: MAC USERS: If you are using the docker version of buildrunner and are getting an error that
   docker-credential-<key> is ``not installed or not available in PATH``, you can do one of the following:

   1. If the authentication information for the docker registry in question is in your
      ``$HOME/.docker/config.json``, remove ``"credsStore" : "osxkeychain"`` and try again
   2. Use this `BASH <https://github.com/adobe/buildrunner/blob/master/scripts/buildrunnerOSXCredStore>`__ script along
      with this `python <https://github.com/adobe/buildrunner/blob/master/scripts/resolve-config.py>`_
      script. This will pull the docker credentials from the OSX keychain and inject them into the docker container