#!/usr/bin/env python3
"""Audit a binary SDK wheel or its installed runtime without accessing hardware."""

import argparse
import importlib
import platform
import struct
import sys
import sysconfig
import zipfile
from email.parser import Parser
from pathlib import Path, PurePosixPath


PACKAGE = "beingbeyond_d1_edu_sdk"
CORE_NAMES = (
    "_dex_hand_core",
    "_head_arm_core",
    "_kinematics_core",
    "_exo_core",
)
SOURCE_SUFFIXES = {".pyx", ".pxd", ".pxi", ".c", ".cpp", ".cc", ".h", ".hpp"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def target_info():
    require(sys.implementation.name == "cpython", "CPython is required")
    require(platform.system() == "Linux", "Linux is required")
    machines = {"x86_64": 62, "amd64": 62, "aarch64": 183, "arm64": 183}
    machine = platform.machine().lower()
    require(machine in machines, "unsupported CPU architecture: " + machine)
    tag = "cp{}{}".format(sys.version_info.major, sys.version_info.minor)
    abi = tag + getattr(sys, "abiflags", "")
    platform_tag = sysconfig.get_platform().replace("-", "_").replace(".", "_")
    suffix = sysconfig.get_config_var("EXT_SUFFIX")
    require(bool(suffix), "interpreter did not provide EXT_SUFFIX")
    return tag, abi, platform_tag, suffix, machines[machine]


def audit_elf(header, label, machine):
    require(len(header) >= 20 and header[:4] == b"\x7fELF", label + ": not an ELF file")
    require(header[4] == 2, label + ": expected a 64-bit ELF file")
    require(header[5] == 1, label + ": expected a little-endian ELF file")
    elf_type, actual_machine = struct.unpack_from("<HH", header, 16)
    require(elf_type == 3, label + ": expected a shared object (ET_DYN)")
    require(actual_machine == machine,
            "{}: ELF machine {}, expected {}".format(label, actual_machine, machine))


def check_wheel(wheel):
    wheel = Path(wheel).resolve()
    python_tag, abi_tag, platform_tag, suffix, machine = target_info()
    expected_tag = "-".join((python_tag, abi_tag, platform_tag))
    require(wheel.name.endswith("-" + expected_tag + ".whl"),
            "wheel filename must target the current interpreter: " + expected_tag)
    core_prefix = PACKAGE + "/core/"
    expected_extensions = {core_prefix + name + suffix for name in CORE_NAMES}
    with zipfile.ZipFile(str(wheel)) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "wheel contains duplicate entries")
        for name in names:
            path = PurePosixPath(name)
            require(not path.is_absolute() and ".." not in path.parts,
                    "wheel contains unsafe path: " + name)
        files = {name for name in names if not name.endswith("/")}
        core_files = {name for name in files if name.startswith(core_prefix)}
        expected_core = expected_extensions | {core_prefix + "__init__.py"}
        require(core_files == expected_core,
                "unexpected core files or missing extensions: " + ", ".join(sorted(core_files ^ expected_core)))
        source_files = {name for name in files if PurePosixPath(name).suffix.lower() in SOURCE_SUFFIXES}
        require(not source_files, "wheel contains source/generated C files: " + ", ".join(sorted(source_files)))
        binaries = {name for name in files if name.endswith((".so", ".pyd", ".dll", ".dylib")) or ".so." in name}
        require(binaries == expected_extensions,
                "wheel contains unexpected binary files: " + ", ".join(sorted(binaries ^ expected_extensions)))
        for name in sorted(expected_extensions):
            with archive.open(name) as stream:
                audit_elf(stream.read(20), name, machine)
        wheel_metadata = [name for name in files if name.endswith(".dist-info/WHEEL")]
        require(len(wheel_metadata) == 1, "expected exactly one WHEEL metadata file")
        metadata = Parser().parsestr(archive.read(wheel_metadata[0]).decode("utf-8"))
        require(metadata.get_all("Tag") == [expected_tag], "WHEEL metadata tag does not match interpreter")
        require(metadata.get("Root-Is-Purelib", "").lower() == "false", "wheel must be a platform binary wheel")
        asset_prefix = PACKAGE + "/BeingBeyond_D1_edu/"
        require(asset_prefix + "robot_right_hand.urdf" in files, "robot URDF is missing")
        require(any(name.startswith(asset_prefix + "meshes/") and name.lower().endswith(".stl") for name in files),
                "robot mesh assets are missing")
    print("PASS wheel: {} (4 matching ELF extensions; no core source; URDF/meshes present)".format(wheel.name))


def is_within(path, directory):
    try:
        path.relative_to(directory)
        return True
    except ValueError:
        return False


def check_runtime(expected_prefix):
    _, _, _, suffix, machine = target_info()
    prefix = Path(expected_prefix if expected_prefix else sys.prefix).resolve()
    require(Path(sys.prefix).resolve() == prefix, "active Python prefix does not match --expected-prefix")
    roots = {Path(sysconfig.get_path(name)).resolve() for name in ("purelib", "platlib")}
    require(all(is_within(root, prefix) for root in roots), "Python installation paths are outside the expected prefix")

    def installed_path(module):
        path = Path(module.__file__).resolve()
        require(any(is_within(path, root) for root in roots),
                "module must come from installed site-packages, not the source tree: " + str(path))
        return path

    package = importlib.import_module(PACKAGE)
    package_dir = installed_path(package).parent
    for name in CORE_NAMES:
        module = importlib.import_module(PACKAGE + ".core." + name)
        path = installed_path(module)
        require(path.name == name + suffix, "extension ABI suffix mismatch: " + str(path))
        with path.open("rb") as stream:
            audit_elf(stream.read(20), str(path), machine)
    core_dir = package_dir / "core"
    allowed = {"__init__.py"} | {name + suffix for name in CORE_NAMES}
    for path in core_dir.iterdir():
        require(path.name == "__pycache__" or path.name in allowed,
                "unexpected file in installed core: " + str(path))

    urdf_module = importlib.import_module(PACKAGE + ".urdf_path")
    installed_path(urdf_module)
    urdf = Path(urdf_module.get_default_urdf_path()).resolve()
    require(urdf.is_file() and is_within(urdf, package_dir), "URDF must exist inside the installed SDK")
    import numpy as np
    import pinocchio as pin

    model, collision, visual = pin.buildModelsFromUrdf(str(urdf), package_dirs=[str(urdf.parent)])
    require(model.nq > 0 and model.nv > 0, "URDF has no movable joints")
    mesh_count = 0
    for geometry in (collision, visual):
        for item in geometry.geometryObjects:
            mesh_path = getattr(item, "meshPath", "")
            if mesh_path:
                require(Path(mesh_path).is_file(), "mesh cannot be resolved: " + mesh_path)
                mesh_count += 1
    require(mesh_count > 0, "URDF did not load any mesh geometry")
    data = model.createData()
    pin.forwardKinematics(model, data, pin.neutral(model))
    pin.updateFramePlacements(model, data)
    require(all(np.isfinite(transform.homogeneous).all() for transform in data.oMf),
            "forward kinematics produced non-finite transforms")

    import cvxpy as cp

    solver = next((name for name in ("CLARABEL", "OSQP", "ECOS", "SCS")
                   if name in cp.installed_solvers()), None)
    require(solver is not None, "CVXPY has no supported installed QP solver")
    variable = cp.Variable(2)
    target = np.array([2.0, -0.25])
    problem = cp.Problem(cp.Minimize(cp.sum_squares(variable - target)),
                         [variable >= -1.0, variable <= 1.0])
    problem.solve(solver=solver)
    require(problem.status in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE),
            "CVXPY QP did not solve: " + str(problem.status))
    require(variable.value is not None and np.allclose(variable.value, [1.0, -0.25], atol=1e-3),
            "CVXPY QP solution is incorrect")
    print("PASS runtime: {} (4 installed ELF extensions; URDF/meshes load; neutral FK finite; QP {})".format(
        prefix, solver))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, help="audit a wheel for this interpreter/CPU")
    parser.add_argument("--runtime", action="store_true", help="check installed SDK and neutral FK, without hardware")
    parser.add_argument("--expected-prefix", help="require this venv/Conda prefix in runtime mode")
    args = parser.parse_args()
    if not args.wheel and not args.runtime:
        parser.error("provide --wheel and/or --runtime")
    if args.expected_prefix and not args.runtime:
        parser.error("--expected-prefix requires --runtime")
    try:
        if args.wheel:
            check_wheel(args.wheel)
        if args.runtime:
            check_runtime(args.expected_prefix)
    except Exception as error:
        print("FAIL: {}: {}".format(type(error).__name__, error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
