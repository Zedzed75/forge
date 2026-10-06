"""Pipeline domain plugin: the integration and deployment chain.

The domain that **federates the others without knowing them**. There is not a
single occurrence of "ansible", "helm" or "terraform" in this package, outside
documentation: everything it knows about the other domains reaches it through the
`GenerationContext` the core assembles from hooks that already existed.
"""
