"""3D model loader for preview panel.

Supports glTF/GLB, OBJ, and FBX formats using trimesh and pyassimp.
"""

from pathlib import Path
from typing import TYPE_CHECKING
import logging

if TYPE_CHECKING:
    import pyvista as pv

logger = logging.getLogger(__name__)

# Supported 3D model formats
SUPPORTED_3D_FORMATS = {".gltf", ".glb", ".obj", ".fbx"}

# Formats supported by trimesh directly
TRIMESH_FORMATS = {".gltf", ".glb", ".obj"}

# Formats that need assimp
ASSIMP_FORMATS = {".fbx"}

# Check library availability
_TRIMESH_AVAILABLE = False
_PYVISTA_AVAILABLE = False
_ASSIMP_AVAILABLE = False

try:
    import trimesh

    _TRIMESH_AVAILABLE = True
except ImportError:
    trimesh = None

try:
    import pyvista as pv

    _PYVISTA_AVAILABLE = True
except ImportError:
    pv = None

try:
    import pyassimp

    _ASSIMP_AVAILABLE = True
except ImportError:
    pyassimp = None


def is_available() -> bool:
    """Check if 3D viewer libraries are available."""
    return _PYVISTA_AVAILABLE and _TRIMESH_AVAILABLE


def get_missing_libraries() -> list[str]:
    """Get list of missing libraries for 3D viewing."""
    missing = []
    if not _PYVISTA_AVAILABLE:
        missing.append("pyvista")
    if not _TRIMESH_AVAILABLE:
        missing.append("trimesh")
    if not _ASSIMP_AVAILABLE:
        missing.append("pyassimp")
    return missing


def is_supported_format(path: Path) -> bool:
    """Check if file format is supported for 3D preview."""
    return path.suffix.lower() in SUPPORTED_3D_FORMATS


def load_mesh(path: Path) -> "pv.PolyData | None":
    """Load a 3D model file and return as PyVista mesh.

    Args:
        path: Path to the 3D model file

    Returns:
        PyVista PolyData mesh, or None if loading failed
    """
    if not is_available():
        logger.warning("3D viewer libraries not available")
        return None

    suffix = path.suffix.lower()

    try:
        if suffix in TRIMESH_FORMATS:
            return _load_with_trimesh(path)
        elif suffix in ASSIMP_FORMATS:
            return _load_with_assimp(path)
        else:
            logger.warning(f"Unsupported 3D format: {suffix}")
            return None
    except Exception as e:
        logger.error(f"Failed to load 3D model {path}: {e}")
        return None


def _load_with_trimesh(path: Path) -> "pv.PolyData | None":
    """Load model using trimesh (glTF, GLB, OBJ)."""
    if not _TRIMESH_AVAILABLE or not _PYVISTA_AVAILABLE:
        return None

    try:
        # Load with trimesh
        mesh = trimesh.load(str(path), force="mesh")

        # Handle scene (multiple meshes)
        if isinstance(mesh, trimesh.Scene):
            # Combine all meshes in the scene
            if len(mesh.geometry) == 0:
                return None
            combined = trimesh.util.concatenate(list(mesh.geometry.values()))
            mesh = combined

        # Convert to PyVista
        if hasattr(mesh, "vertices") and hasattr(mesh, "faces"):
            import numpy as np

            vertices = np.array(mesh.vertices)
            faces = np.array(mesh.faces)

            # PyVista expects faces in format: [n, v0, v1, v2, n, v0, v1, v2, ...]
            n_faces = len(faces)
            pv_faces = np.column_stack([np.full(n_faces, 3), faces]).ravel()

            return pv.PolyData(vertices, pv_faces)
        else:
            logger.warning(f"Loaded mesh has no vertices/faces: {path}")
            return None

    except Exception as e:
        logger.error(f"trimesh failed to load {path}: {e}")
        return None


def _load_with_assimp(path: Path) -> "pv.PolyData | None":
    """Load model using pyassimp (FBX and other formats)."""
    if not _ASSIMP_AVAILABLE or not _PYVISTA_AVAILABLE:
        logger.warning("pyassimp not available for FBX loading")
        return None

    try:
        import numpy as np

        scene = pyassimp.load(str(path))

        all_vertices = []
        all_faces = []
        vertex_offset = 0

        for mesh in scene.meshes:
            vertices = mesh.vertices
            all_vertices.append(vertices)

            # Offset faces by current vertex count
            for face in mesh.faces:
                all_faces.append([len(face)] + [idx + vertex_offset for idx in face])

            vertex_offset += len(vertices)

        pyassimp.release(scene)

        if not all_vertices:
            return None

        # Combine all vertices
        combined_vertices = np.vstack(all_vertices)

        # Flatten faces
        pv_faces = np.array([item for face in all_faces for item in face])

        return pv.PolyData(combined_vertices, pv_faces)

    except Exception as e:
        logger.error(f"pyassimp failed to load {path}: {e}")
        return None
