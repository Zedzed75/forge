"""Enumerations of the pipeline domain."""

from __future__ import annotations

from enum import Enum


class Provider(str, Enum):
    """Targeted continuous integration tool.

    The choice changes the **format of the file**, never what it contains: the
    same jobs, derived from the same context, are written in both dialects. That
    is the only reason two templates coexist.
    """

    #: GitHub Actions — `.github/workflows/ci.yml`.
    GITHUB = "github"

    #: GitLab CI — `.gitlab-ci.yml`.
    GITLAB = "gitlab"


class JobKind(str, Enum):
    """Nature of a generated job. Fixes its stage and its dependencies."""

    #: Validation of a domain: its own `Command`s, as it declares them.
    VALIDATE = "validate"

    #: Build and publication of the service image.
    BUILD = "build"

    #: Deployment of an environment, one job per environment.
    DEPLOY = "deploy"
