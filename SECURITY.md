# Security Policy

Security fixes are provided for the latest stable UserDock release.

Report vulnerabilities with GitHub's private vulnerability reporting feature.
Do not disclose suspected vulnerabilities in a public issue. Include the
affected version, Linux distribution, reproduction steps, and security impact,
but never include real passwords, tokens, or private account data.

UserDock requires effective root privileges and refuses normal execution by an
unprivileged process. It invokes account tools with validated argument lists
and never through a command shell. UserDock is not installed setuid.

