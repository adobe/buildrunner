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
3. Install dependencies

.. code:: bash

  uv sync

4. Run the tests

    Run all the tests by typing `uv run pytest`

    .. code:: bash

        uv run pytest


    To run a specific test file, provide the path to the file

    .. code:: bash

        uv run pytest tests/test_buildrunner.py


Locally
-----------

To run buildrunner locally in the buildrunner directory, use ``uv run``. This ensures that the
latest local changes are used when running buildrunner. The `examples/` directory
contains example buildrunner configuration files that can be used to test the
functionality of buildrunner.
To run buildrunner locally follow these steps:

1. Clone the `buildrunner repository <https://github.com/adobe/buildrunner>`_

.. code:: bash

  git clone https://github.com/adobe/buildrunner.git

2. Navigate to the root of the buildrunner repository
3. Install dependencies

.. code:: bash

  uv sync

4. Run buildrunner

.. code:: bash

  uv run buildrunner -f examples/build/basic/buildrunner.yaml


Another repository
------------------------------------------------
It is also possible to install and run a working version of buildrunner in another repository.
To do this, follow these steps:

1. Clone the `buildrunner repository <https://github.com/adobe/buildrunner>`_

.. code:: bash

  git clone https://github.com/adobe/buildrunner.git

2. Navigate to the root of the desired repository
3. Install buildrunner

.. code:: bash

  uv tool install ..</path/to>/buildrunner

4. Run buildrunner

.. code:: bash

    buildrunner --help

.. note::

   You can verify that you are using the correct buildrunner by typing ``which buildrunner``.

