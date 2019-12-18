###################
 Buildrunner Tests
###################

This is a test suite for Buildrunner.  It combines unit tests (``.py`` files) as well as complete,
run-time invocation tests (``.yaml`` files).

This utilizes the ``xfail`` setting for Buildrunner steps.

Only build files that start with ``test-`` and have a ``.yaml`` suffix will be considered.

Files that begin with ``test-xfail`` are expected to fail.

..
   Local Variables:
   fill-column: 100
   End:
