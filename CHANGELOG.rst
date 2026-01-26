###########
 Changelog
###########

.. contents::
   :local:

3.0
###

* 3.17

  * Add python 3.13 support
  * Migrate to uv for dependency management
  * Optimize Docker build context: source directory is no longer copied when path is not explicitly specified, improving build performance when using only inject or dockerfile attributes

* ... undocumented versions, see GitHub tagged releases ...

* 3.0

  * Add python 3.11 support
  * Remove python 3.6 and 3.7 support

2.0
###

* 2.0

  * Add step dependencies feature in configuration
  * Add version to config file

1.3
###

* 1.3.2

  * Fix compatibility with Python 3.6

* 1.3.1

  * Fix docker image command

* 1.3.0

  * Add platform flag (PR #7)

1.2
###

* 1.2.0

  * Build and publish docker images, including arm versions
  * Upgrade dependency versions

..
   Local Variables:
   fill-column: 100
   End:
