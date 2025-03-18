##############
 Development
##############

This guide provides instructions for running tests and executing `buildrunner` locally during development.

Unit tests
----------

The unit tests use `pytest <https://docs.pytest.org/en/latest/>`_.
To run the tests, execute the following commands:

1. Clone the `buildrunner repository <https://github.com/adobe/buildrunner>`_

.. code:: bash

  git clone https://github.com/adobe/buildrunner.git

2. Navigate to the root of the buildrunner repository
3. Setup virtual environment

.. code:: bash

  python -m venv venv
  source venv/bin/activate

4. Install requirements

.. code:: bash

  pip install -r requirements.txt

4. Install test requirements

.. code:: bash

  pip install -r test_requirements.txt

5. Run the tests

    Run all the tests by typing `pytest`

    .. code:: bash

        pytest


    To run a specific test file, provide the path to the file

    .. code:: bash

        pytest tests/test_buildrunner.py


Locally
-----------

To run buildrunner locally in the buildrunner directory it is best to use
the `run-buildrunner.sh <../run-buildrunner.sh>`_ script. This ensures that the
latest local changes are used when running buildrunner. The `examples/` directory
contains example buildrunner configuration files that can be used to test the
functionality of buildrunner.
To use this script follow these steps:

1. Clone the `buildrunner repository <https://github.com/adobe/buildrunner>`_

.. code:: bash

  git clone https://github.com/adobe/buildrunner.git

2. Navigate to the root of the buildrunner repository
3. Setup virtual environment

.. code:: bash

  python -m venv venv
  source venv/bin/activate

4. Install requirements

.. code:: bash

  pip install -r requirements.txt

5. Run the script

.. code:: bash

  ./run-buildrunner.sh -f examples/build/basic/buildrunner.yaml


Another repository
------------------------------------------------
It is also possible to install and run a working version of buildrunner in another repository.
To do this, follow these steps:

1. Clone the `buildrunner repository <https://github.com/adobe/buildrunner>`_

.. code:: bash

  git clone https://github.com/adobe/buildrunner.git

2. Navigate to the root of the desired repository
3. Setup virtual environment

.. code:: bash

  python -m venv venv
  source venv/bin/activate

4. Install buildrunner

.. code:: bash

  pip install ..</path/to>/buildrunner

5. Reactivate the virtual environment

.. code:: bash

  deactivate
  source venv/bin/activate

6. Run buildrunner

.. code:: bash

    buildrunner --help

.. note::

    You can verify that you are using the correct buildrunner by typing "`which buildrunner`"
    and ensuring that the path is to the virtual environment (i.e. `venv/`).
