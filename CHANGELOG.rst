###########
 Changelog
###########

.. contents::
   :local:

Unreleased
##########

* Honor RSA/SHA-2 signature requests in the forwarded SSH agent, allowing
  injected RSA keys to work with strict SSH clients such as Rocky Linux 10.
  Zero-flag RSA requests retain legacy ``ssh-rsa``/SHA-1 signing; non-RSA
  signing behavior is unchanged.
* Reject malformed or unsupported signing flags rather than silently ignoring
  them. RSA-specific flags are rejected for non-RSA keys.
* No dependency upgrade is required: the existing Paramiko requirement
  (``>=2.10.3,<4.0.0``) already supports RSA/SHA-2 signing, and the lock file
  already selects Paramiko 3.5.1. The existing failure response (5) is unchanged.

.. warning::

   Custom agent clients must provide a complete 32-bit signing-flags field
   and use only supported flags. Requests that were previously accepted with
   ignored or incomplete flags now receive an explicit failure response.
   SHA-1 is not enabled globally, and this fix does not bypass key-size or
   crypto-policy restrictions. The same RSA key can produce both SHA-1 and
   SHA-2 signatures; key age and signature algorithm are separate concerns.

   Opt-in Docker smoke tests exercise the real agent proxy, forwarding,
   injected-key fingerprint matching, server-side signature verification,
   artifact capture, and cleanup. Rocky 10 checks default negotiation and
   both RSA/SHA-2 algorithms; a separate Rocky 8 job verifies legacy
   ``ssh-rsa``/SHA-1 using the same traditional PEM, 2048-bit RSA key without
   relaxing the Rocky 10 server's SHA-2-only configuration. See
   ``tests/sshagent-rocky10/README.rst`` for reproduction instructions.
   The full test suite, production SSH endpoints, and Fabric remote tasks
   have not been validated. Canary the updated worker installation before
   broad rollout.

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
