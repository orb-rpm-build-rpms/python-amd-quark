%global pypi_name amd-quark
# Upstream import package is "quark" (not "amd_quark").
%global import_name quark
# The GitHub source tag is v0.12; the tagged tree's quark/version.txt reads
# "0.12.post1". That base version reaches the wheel unchanged ONLY on a release
# build: setup.py's get_version() returns the version.txt string verbatim when
# QUARK_RELEASE is truthy, but otherwise appends a "+<git-hash>" local segment
# (from `git rev-parse`, which yields "unknown" on this .git-less tarball). Both
# the local segment and any accelerator suffix would break vLLM's exact pin
# (amd-quark==0.12.post1), so the build below exports QUARK_RELEASE=1 and keeps
# torch out of the build environment (an accelerator suffix like "+rocm70.torchX"
# is added only when torch is importable). The source tarball unpacks to
# quark-0.12.
%global src_version 0.12

Name:           python-%{pypi_name}
# NOTE: Fedora's guideline spells a post-release "0.12^post1"; this keeps the
# upstream string verbatim because the dependency that matters -- the
# python3dist(amd-quark) Provide consumed by vLLM's "==0.12.post1" pin -- is
# generated from the wheel's own metadata (quark/version.txt = 0.12.post1), not
# from this field.
Version:        0.12.post1
Release:        %autorelease
Summary:        AMD Quark: a cross-platform quantization toolkit for PyTorch and ONNX models

License:        MIT
URL:            https://github.com/amd/quark
# amd-quark is wheel-only on PyPI from 0.6.0 onward (no sdist for 0.12.post1), so
# build from the GitHub v0.12 tag instead.
Source0:        %{url}/archive/refs/tags/v%{src_version}.tar.gz#/%{import_name}-%{src_version}.tar.gz

# Pure Python: the upstream 0.12.post1 wheel on PyPI is py3-none-any. quark does
# carry optional C/C++/HIP sources for a torch-linked "_C" extension (ONNX
# Runtime custom ops, fake-quant kernels), but that extension is absent from the
# published wheel and is not required by vLLM's quark integration, so it is NOT
# built here (see the torch handling in %prep). Building it would make the
# package arch-ful, pull in ONNX Runtime, and add a torch-ABI local-version tag
# to the wheel -- out of scope for this foundation.
BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  python3dist(setuptools) >= 61
BuildRequires:  python3dist(wheel)
# setup.py unconditionally shells out to `git rev-parse` (for version.py's
# git_version stamp) even on a release build; on this .git-less tarball that
# exits non-zero and is caught, but the git binary must exist or it raises
# FileNotFoundError and aborts.
BuildRequires:  git-core

%global desc %{expand:
AMD Quark is a cross-platform quantization toolkit for deep learning models,
supporting both PyTorch and ONNX. It helps optimize models for deployment across
a range of hardware backends while preserving accuracy.}

%description
%{desc}

%package -n     python3-%{pypi_name}
Summary:        %{summary}
# torch is a hard runtime dependency of quark's PyTorch quantization path, but
# upstream lists it only under [build-system].requires -- never in the runtime
# metadata -- so the automatic dependency generator cannot emit it. Add it here.
Requires:       python3dist(torch)
# TODO: onnx is capped hard at >=1.21.0,<=1.22.0 by upstream. Confirm the base
# repo / localrepo ship an onnx in that window; if not, it must be built too.
# The remaining runtime deps (numpy>=2.0, onnxscript, onnxslim, pandas, plotly,
# protobuf, psutil, pydantic, rich, scipy, sentencepiece, tqdm, zstandard,
# evaluate, joblib, ninja) are emitted automatically by the dependency generator.

%description -n python3-%{pypi_name}
%{desc}

%prep
%autosetup -p1 -n %{import_name}-%{src_version}

# 1) Allow Python 3.14. Upstream caps requires-python at "<3.14" (F44 ships
#    3.14); the package is pure Python, so relax the cap to match vLLM's own
#    "<3.15" upper bound.
sed -i 's/requires-python = ">=3.11,<3.14"/requires-python = ">=3.11,<3.15"/' pyproject.toml

# 2) Drop torch from the build backend requirements so the build does not try to
#    pull it and, more importantly, so setup.py takes its "torch not importable"
#    path and skips compiling the optional _C extension -- producing the same
#    pure-Python wheel AMD publishes. (torch is still a runtime Requires above.)
sed -i '/^\s*"torch>=2\.2\.0",\s*$/d' pyproject.toml

# QUARK_RELEASE=1 makes setup.py's get_version() emit version.txt verbatim
# (0.12.post1) instead of appending a "+<git-hash>" local segment. It must be set
# for every phase that runs setup.py -- metadata generation, the wheel build, and
# save-files (which reads the installed dist-info) -- so the version is consistent
# throughout. rpm's %%global cannot export a shell variable, so it is exported in
# each section.
%generate_buildrequires
export QUARK_RELEASE=1
# With torch stripped from the build backend requirements, this installs only the
# runtime/build deps needed to produce the pure-Python wheel.
%pyproject_buildrequires

%build
export QUARK_RELEASE=1
%pyproject_wheel

%install
export QUARK_RELEASE=1
%pyproject_install
%pyproject_save_files -l %{import_name}

%check
# Importing quark pulls in torch and the heavy ONNX stack; a plain import check
# is reasonable once those deps are confirmed present in the build root.
# TODO: enable the pyproject import-check macro for the quark package after
# verifying onnx (>=1.21,<=1.22) and torch resolve in the build root.

%files -n python3-%{pypi_name} -f %{pyproject_files}
%license LICENSE
%doc README.md

%changelog
%autochangelog
