# Packaging notes: python-amd-quark

These notes explain the non-obvious choices in `python-amd-quark.spec` and their
consequences for a ROCm vLLM deployment. They complement the inline comments in
the spec; the spec remains the source of truth for the mechanics.

## What this package ships

A **pure-Python, noarch** wheel equivalent to the generic `py3-none-any`
`amd-quark` wheel AMD publishes on PyPI. It contains **no** compiled `_C`
extension.

This is deliberate, and it matters because vLLM's `requirements/rocm.txt` pins
`amd-quark==0.12.post1` — the *generic* PyPI wheel. AMD also builds separate
accelerator-specific wheels that bundle a compiled `_C` and carry a local version
tag like `+rocm70.torch2.12`; vLLM does **not** pin those. Reproducing the
generic wheel is therefore faithful to what a normal `pip install` of vLLM's
pinned dependency resolves to on ROCm.

## Why torch is kept out of the build environment

quark's `setup.py` keys two things solely on `import torch` succeeding, with no
override switch:

1. **The `_C` extension is compiled.** Building it would make the package
   arch-specific and pull in ONNX Runtime headers.
2. **An accelerator suffix is appended to the version.** Even for a release build
   (`QUARK_RELEASE=1`), the version becomes `version.txt` + accelerator suffix, so
   a torch-in-build environment yields `0.12.post1+rocm70.torch2.12` instead of
   `0.12.post1`.

RPM installs `BuildRequires` for the whole build, not just one phase, so listing
torch there would trigger both effects and break vLLM's exact `==0.12.post1`
pin. torch is a genuine runtime dependency and is declared as a manual `Requires`
instead.

A side effect: because torch is absent at build time, there is no import test in
`%check` (importing quark's torch path needs torch). The wheel that ships is the
same pure-Python artifact AMD builds and tests upstream.

## ROCm acceleration is preserved — via runtime JIT

Shipping no `_C` does **not** remove GPU acceleration. quark's quantization math
runs on whatever device its torch tensors live on, so on a ROCm torch it runs on
the AMD GPU.

The fused hw_emulation kernel is resolved when
`quark.torch.kernel.hw_emulation.extensions` is imported (which happens on quark's
torch path, the path vLLM uses). The loader prefers a prebuilt `_C`; finding none,
it **JIT-compiles the kernel at runtime** against the installed ROCm torch,
honoring `PYTORCH_ROCM_ARCH`. The result is the same GPU kernel, compiled on the
deployment host on first use rather than baked into the package.

### Deployment requirement

Because the kernel is compiled at runtime, the **deployment host** must provide:

- a HIP/C++ compiler and the ROCm and torch development headers, and
- a writable torch extension cache.

On torch >= 2.10 (this stack uses 2.12) the loader treats a failure of *both* the
prebuilt load *and* the JIT compile as a **hard error** at import — it does not
fall back to a slow pure-Python path. A minimal runtime container without the
build toolchain will therefore fail rather than silently degrade. Provision the
ROCm build tooling in the inference image, or pre-warm the extension cache.

## Trimmed dependencies

quark's `pyproject.toml` declares `dependencies = {file = ["requirements.txt"]}`,
so its entire flat requirements list becomes `install_requires`. That list spans
quark's two independent halves — PyTorch quantization and ONNX quantization —
even though a consumer typically needs only one.

vLLM imports only `quark.torch` (the mx kernel, `quantization.utils`,
`utils.pack`, and hw_emulation), none of which load the ONNX or plotting/eval
libraries. The spec strips `onnx`, `onnxscript`, `onnxslim`, `plotly`, and
`evaluate` from `requirements.txt` in `%prep`, which removes them from both the
build environment and the generated runtime `Requires`. This avoids packaging the
ONNX toolchain (and its own onnx/onnxruntime chains) for a code path this
deployment never exercises. The remaining dependencies are all present in the
Fedora base.

If a consumer of this package *does* need quark's ONNX quantization, those
dependencies would have to be packaged and the trim narrowed accordingly.
