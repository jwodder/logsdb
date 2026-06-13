|repostatus| |ci-status| |license|

.. |repostatus| image:: https://www.repostatus.org/badges/latest/concept.svg
    :target: https://www.repostatus.org/#concept
    :alt: Project Status: Concept – Minimal or no implementation has been done
          yet, or the repository is only intended to be a limited example,
          demo, or proof-of-concept.

.. |ci-status| image:: https://github.com/jwodder/logsdb/actions/workflows/test.yml/badge.svg
    :target: https://github.com/jwodder/logsdb/actions/workflows/test.yml
    :alt: CI Status

.. |license| image:: https://img.shields.io/github/license/jwodder/logsdb.svg
    :target: https://opensource.org/licenses/MIT
    :alt: MIT License

`GitHub <https://github.com/jwodder/logsdb>`_
| `Issues <https://github.com/jwodder/logsdb/issues>`_

``logsdb`` is a Python package for personal use that provides commands for
logging various activity on a server (web server requests, attempted SSH
logins, and received e-mails) and sending a daily e-mail with a summary.  It is
meant to be installed via the Ansible playbook at
<https://github.com/jwodder/system>.
