"""
core/transfer.py - Animation transfer engine for ReAnimate Tool.
Supports multiple transfer modes with automatic bind-pose detection.
"""

import math
import traceback
import maya.cmds as cmd
import maya.api.OpenMaya as om


# --- Public API ---

def transfer_animation(mappings, start_frame, end_frame,
                       bind_pose_frame=None,
                       frame_offset=0,
                       bind_search_range=10):
    """
    Transfer animation from source to target joints per mapping.

    Supported modes: Transfer, Overwrite, Keep, Ignore,
    Transfer (World), Transfer (Hybrid Local), Transfer (Hybrid World),
    Transfer (Quaternion), Transfer (Matrix).

    Bind-pose corrections are computed automatically unless bind_pose_frame is provided.
    """
    try:
        if not mappings:
            cmd.warning("No mappings provided for transfer.")
            return

        filtered = [m for m in mappings if (m.get("mode") or "Transfer").lower() != "ignore"]
        if not filtered:
            cmd.inViewMessage(amg="No mappings to process (all ignored).", pos="midCenter", fade=True)
            return

        # Overwrite pre-pass — clear existing keys on target attributes
        for m in filtered:
            if (m.get("mode") or "Transfer").lower() != "overwrite":
                continue
            src, tgt, attrs = m.get("source", ""), m.get("target", ""), m.get("attrs", []) or []
            if not src or not tgt:
                continue
            for attr in attrs:
                try:
                    if cmd.objExists(f"{tgt}.{attr}"):
                        cmd.cutKey(tgt, time=(start_frame + frame_offset, end_frame + frame_offset), attribute=attr)
                except Exception:
                    pass

        work_list = [
            (m.get("source", ""), m.get("target", ""), tuple(m.get("attrs", []) or []), (m.get("mode") or "Transfer"))
            for m in filtered
        ]

        # Bind-pose correction
        if bind_pose_frame is not None:
            corrections = compute_bind_corrections_from_frame(work_list, bind_pose_frame)
        else:
            search_end = min(int(start_frame) + int(bind_search_range), int(end_frame))
            corrections = compute_bind_corrections_auto(work_list, int(start_frame), search_end)

        # Optional bind-pose key before baking
        if bind_pose_frame is not None:
            for src, tgt, attrs, mode in work_list:
                if not cmd.objExists(src) or not cmd.objExists(tgt):
                    continue
                _set_current_time(bind_pose_frame)
                for attr in attrs:
                    src_attr, tgt_attr = f"{src}.{attr}", f"{tgt}.{attr}"
                    if not cmd.objExists(src_attr) or not cmd.objExists(tgt_attr):
                        continue
                    try:
                        cmd.setKeyframe(tgt_attr, time=bind_pose_frame + frame_offset,
                                        value=cmd.getAttr(src_attr))
                    except Exception:
                        pass

        total_frames = int(end_frame) - int(start_frame) + 1
        cmd.progressWindow(
            title="Transferring Animation",
            progress=0,
            status="Baking frames...",
            isInterruptable=True,
            maxValue=total_frames
        )
        cmd.undoInfo(openChunk=True)

        try:
            try:
                cmd.refresh(suspend=True)
            except Exception:
                pass

            for frame_idx, frame in enumerate(range(int(start_frame), int(end_frame) + 1), start=1):
                if cmd.progressWindow(query=True, isCancelled=True):
                    cmd.warning("Animation transfer cancelled by user.")
                    break

                _set_current_time(frame)
                cmd.progressWindow(edit=True, progress=frame_idx,
                                   status=f"Baking frame {frame} ({frame_idx}/{total_frames})")

                for src, tgt, attrs, mode in work_list:
                    if not cmd.objExists(src) or not cmd.objExists(tgt):
                        continue
                    if mode.lower() == "keep":
                        continue
                    handler = TRANSFER_MODES.get(mode.lower(), TRANSFER_MODES["transfer"])
                    try:
                        handler(src, tgt, frame, frame_offset, attrs, mode, corrections)
                    except Exception as ex:
                        cmd.warning(f"Transfer failed for {src}->{tgt} mode={mode}: {ex}")

        finally:
            try:
                cmd.refresh(suspend=False)
            except Exception:
                pass
            try:
                cmd.progressWindow(endProgress=True)
            except Exception:
                pass
            try:
                cmd.undoInfo(closeChunk=True)
            except Exception:
                pass

        cmd.inViewMessage(amg="Animation transfer completed", pos="midCenter", fade=True)

    except Exception:
        traceback.print_exc()
        cmd.warning("Transfer failed (see Script Editor).")


# --- Transfer Mode Registry ---

TRANSFER_MODES = {}

def register_mode(name):
    """Decorator to register a transfer mode handler by name."""
    def decorator(func):
        TRANSFER_MODES[name.lower()] = func
        return func
    return decorator


# --- Internal Helpers ---

def _set_current_time(frame):
    """Set Maya's current time, trying both API variants."""
    try:
        cmd.currentTime(frame, edit=True)
    except Exception:
        try:
            cmd.setCurrentTime(frame, edit=True)
        except Exception:
            pass


def _normalize_requested(attrs):
    """Normalize a list of attribute names to a lowercase set for matching."""
    return set((a or "").strip().replace(" ", "").lower() for a in (attrs or []))


def _want(requested_set, name):
    """Return True if the normalized attribute name is in the requested set."""
    return name.replace(" ", "").lower() in requested_set


def _set_rotation_keys(tgt, euler, ft, requested):
    """Set rotation keyframes on a target joint from an MEulerRotation."""
    if _want(requested, "rotatex"): cmd.setKeyframe(tgt, at="rotateX", v=math.degrees(euler.x), t=ft)
    if _want(requested, "rotatey"): cmd.setKeyframe(tgt, at="rotateY", v=math.degrees(euler.y), t=ft)
    if _want(requested, "rotatez"): cmd.setKeyframe(tgt, at="rotateZ", v=math.degrees(euler.z), t=ft)


def _apply_rotate_order(euler, tgt):
    """Reorder euler rotation to match target's rotateOrder."""
    try:
        euler.reorderIt(int(cmd.getAttr(tgt + ".rotateOrder")))
    except Exception:
        pass
    return euler


def _quat_to_euler(q, tgt):
    """Convert a quaternion to euler and apply the target's rotate order."""
    e = q.asEulerRotation() if isinstance(q, om.MQuaternion) else q
    return _apply_rotate_order(e, tgt)


# --- Mode Handlers ---

@register_mode("transfer")
def mode_transfer(src, tgt, frame, frame_offset, attrs, mode, corrections):
    """Direct attribute value copy from source to target."""
    ft = frame + frame_offset
    for attr in attrs:
        src_attr, tgt_attr = f"{src}.{attr}", f"{tgt}.{attr}"
        try:
            if cmd.objExists(src_attr) and cmd.objExists(tgt_attr):
                cmd.setKeyframe(tgt_attr, time=ft, value=cmd.getAttr(src_attr))
        except Exception:
            pass


@register_mode("transfer (world)")
def mode_transfer_world(src, tgt, frame, frame_offset, attrs, mode, corrections):
    """World-space matrix transfer."""
    apply_world_transfer(src, tgt, frame, frame_offset, attrs)


@register_mode("transfer (hybrid local)")
def mode_transfer_hybrid_a(src, tgt, frame, frame_offset, attrs, mode, corrections):
    """Local-space JO-stripped transfer with bind correction."""
    apply_hybrid_transfer_localJO(src, tgt, frame, frame_offset, attrs, corrections.get((src, tgt)))


@register_mode("transfer (hybrid world)")
def mode_transfer_hybrid_b(src, tgt, frame, frame_offset, attrs, mode, corrections):
    """World-space to local JO-stripped transfer with bind correction."""
    apply_hybrid_transfer_worldJO(src, tgt, frame, frame_offset, attrs, corrections.get((src, tgt)))


@register_mode("transfer (quaternion)")
def mode_transfer_quaternion(src, tgt, frame, frame_offset, attrs, mode, corrections):
    """Quaternion-based rotation transfer via world space."""
    try:
        requested = _normalize_requested(attrs)
        ft = frame + frame_offset
        q_src_world = get_world_quaternion(src)
        parent = cmd.listRelatives(tgt, p=True, f=True)
        q_local = get_world_quaternion(parent[0]).inverse() * q_src_world if parent else q_src_world
        _set_rotation_keys(tgt, _quat_to_euler(q_local, tgt), ft, requested)
    except Exception as ex:
        cmd.warning(f"Quaternion transfer failed for {src}->{tgt} @ {frame}: {ex}")


@register_mode("transfer (matrix)")
def mode_transfer_matrix(src, tgt, frame, frame_offset, attrs, mode, corrections):
    """Full matrix decomposition transfer."""
    try:
        apply_matrix_transfer(src, tgt, frame + (frame_offset or 0), attrs or [])
    except Exception as ex:
        cmd.warning(f"Matrix transfer failed for {src}->{tgt} @ {frame}: {ex}")


# --- Math Helpers ---

def get_world_matrix(node):
    """Return the world matrix of a node as MMatrix."""
    return om.MMatrix(cmd.xform(node, q=True, ws=True, m=True))


def get_world_quaternion(node):
    """Return the world-space rotation of a node as MQuaternion."""
    return om.MTransformationMatrix(get_world_matrix(node)).rotation(asQuaternion=True)


def decompose_matrix(matrix, space=om.MSpace.kWorld):
    """Decompose an MMatrix into translation, quaternion rotation, and scale."""
    tm = om.MTransformationMatrix(matrix)
    return tm.translation(space), tm.rotation(asQuaternion=True), tuple(tm.scale(space))


def _world_to_local_matrix(src, tgt):
    """Compute src world matrix in tgt's local space."""
    src_world = get_world_matrix(src)
    parent = cmd.listRelatives(tgt, parent=True, f=True)
    parent_world = get_world_matrix(parent[0]) if parent else om.MMatrix()
    return src_world * parent_world.inverse()


def _set_trs_keys(tgt, trans, euler, scale, ft, requested):
    """Set translate, rotate, and scale keyframes from decomposed values."""
    if _want(requested, "translatex"): cmd.setKeyframe(tgt, at="translateX", v=trans.x, t=ft)
    if _want(requested, "translatey"): cmd.setKeyframe(tgt, at="translateY", v=trans.y, t=ft)
    if _want(requested, "translatez"): cmd.setKeyframe(tgt, at="translateZ", v=trans.z, t=ft)
    _set_rotation_keys(tgt, euler, ft, requested)
    if scale:
        if _want(requested, "scalex"): cmd.setKeyframe(tgt, at="scaleX", v=scale[0], t=ft)
        if _want(requested, "scaley"): cmd.setKeyframe(tgt, at="scaleY", v=scale[1], t=ft)
        if _want(requested, "scalez"): cmd.setKeyframe(tgt, at="scaleZ", v=scale[2], t=ft)


# --- Transfer Primitives ---

def apply_world_transfer(src, tgt, frame, frame_offset=0, attrs=None):
    """Transfer animation using world-space matrix decomposition."""
    try:
        if not cmd.objExists(src) or not cmd.objExists(tgt):
            return
        requested = _normalize_requested(attrs)
        local_mtx = _world_to_local_matrix(src, tgt)
        trans, quat, scale = decompose_matrix(local_mtx, space=om.MSpace.kObject)
        _set_trs_keys(tgt, trans, _quat_to_euler(quat, tgt), scale, frame + frame_offset, requested)
    except Exception as ex:
        cmd.warning(f"World transfer failed {src}->{tgt} @ {frame}: {ex}")


def apply_matrix_transfer(src, tgt, frame, attrs):
    """Transfer animation using full matrix decomposition without scale."""
    try:
        if not cmd.objExists(src) or not cmd.objExists(tgt):
            return
        requested = _normalize_requested(attrs)
        local_mtx = _world_to_local_matrix(src, tgt)
        trans, quat, _ = decompose_matrix(local_mtx, space=om.MSpace.kObject)
        _set_trs_keys(tgt, trans, _quat_to_euler(quat, tgt), None, frame, requested)
    except Exception as ex:
        cmd.warning(f"Matrix transfer failed {src}->{tgt} @ {frame}: {ex}")


def apply_quaternion_transfer(src, tgt, frame, attrs):
    """Transfer rotation using quaternion world-space conversion."""
    try:
        if not cmd.objExists(src) or not cmd.objExists(tgt):
            return
        requested = _normalize_requested(attrs)
        q_world = get_world_quaternion(src)
        parent = cmd.listRelatives(tgt, p=True, f=True)
        q_local = get_world_quaternion(parent[0]).inverse() * q_world if parent else q_world
        _set_rotation_keys(tgt, _quat_to_euler(q_local, tgt), frame, requested)
    except Exception as ex:
        cmd.warning(f"Quaternion transfer failed {src}->{tgt} @ {frame}: {ex}")


# --- Bind-Pose Detection ---

def compute_bind_corrections_auto(work_list, start_frame, end_frame):
    """
    Auto-detect bind pose by finding the frame with minimum total joint-angle mismatch.
    Returns bind corrections computed at the best frame found.
    """
    if start_frame > end_frame:
        return {}

    frame_scores = {}
    for f in range(start_frame, end_frame + 1):
        _set_current_time(f)
        total_angle = 0.0
        for src, tgt, attrs, mode in work_list:
            if not cmd.objExists(src) or not cmd.objExists(tgt):
                continue
            try:
                _, q_src, _ = decompose_local_matrix(compute_local_matrix(src), src)
                _, q_tgt, _ = decompose_local_matrix(compute_local_matrix(tgt), tgt)
                _, ang = (q_tgt * q_src.inverse()).asAxisAngle()
                total_angle += abs(math.degrees(ang))
            except Exception:
                continue
        frame_scores[f] = total_angle

    if not frame_scores:
        return {}

    best_frame = min(frame_scores, key=lambda k: frame_scores[k])
    return compute_bind_corrections_from_frame(work_list, best_frame)


def compute_bind_corrections_from_frame(work_list, bind_frame):
    """
    Compute quaternion bind-pose corrections for all joint pairs at a given frame.
    Returns dict[(src, tgt)] -> MQuaternion.
    """
    corrections = {}
    _set_current_time(bind_frame)
    for src, tgt, attrs, mode in work_list:
        if not cmd.objExists(src) or not cmd.objExists(tgt):
            continue
        try:
            _, q_src, _ = decompose_local_matrix(compute_local_matrix(src), src)
            _, q_tgt, _ = decompose_local_matrix(compute_local_matrix(tgt), tgt)
            corrections[(src, tgt)] = q_src.inverse() * q_tgt
        except Exception:
            pass
    return corrections


# --- Local-Space Utilities ---

def compute_local_matrix(node):
    """
    Compute the true local matrix of a node:
    M_local = worldMatrix * parentWorldMatrix.inverse()
    """
    sel = om.MSelectionList()
    sel.add(node)
    M_world = sel.getDagPath(0).inclusiveMatrix()
    parent = cmd.listRelatives(node, parent=True, fullPath=True)
    if parent:
        sel2 = om.MSelectionList()
        sel2.add(parent[0])
        M_parent = sel2.getDagPath(0).inclusiveMatrix()
        return M_world * M_parent.inverse()
    return M_world


def strip_joint_orient(node):
    """Return the joint orient of a node as MQuaternion, or identity if not a joint."""
    try:
        if cmd.nodeType(node) != "joint":
            return om.MQuaternion()
        jo = cmd.getAttr(node + ".jointOrient")[0]
        e = om.MEulerRotation(*[math.radians(v) for v in jo], order=om.MEulerRotation.kXYZ)
        return e.asQuaternion()
    except Exception:
        return om.MQuaternion()


def decompose_local_matrix(M_local, node):
    """
    Decompose a local matrix into translation, JO-stripped rotation quaternion, and scale.
    The returned quaternion corresponds to the node's .rotate channels.
    """
    tm = om.MTransformationMatrix(M_local)
    t = tm.translation(om.MSpace.kTransform)
    q_noJO = strip_joint_orient(node).inverse() * tm.rotation(asQuaternion=True)
    s = tm.scale(om.MSpace.kTransform)
    return t, q_noJO, tuple(s)


def compose_local_matrix(translation, quat_noJO, scale, node):
    """
    Compose a local matrix from translation, JO-stripped rotation quaternion, and scale.
    Reapplies joint orient so the resulting matrix includes JO * rotate.
    """
    tm = om.MTransformationMatrix()
    tm.setTranslation(om.MVector(*translation), om.MSpace.kTransform)
    tm.setRotation((strip_joint_orient(node) * quat_noJO).asEulerRotation())
    tm.setScale(scale, om.MSpace.kTransform)
    return tm.asMatrix()


# --- Hybrid Transfer Modes ---

def apply_hybrid_transfer_localJO(src, tgt, frame, frame_offset=0, attrs=None, correction_quat=None):
    """
    Hybrid A: Local-space JO-stripped transfer with optional bind correction.
    Best for rigs with matching local-space orientations.
    """
    try:
        if not cmd.objExists(src) or not cmd.objExists(tgt):
            return
        requested = _normalize_requested(attrs)
        ft = frame + frame_offset
        T_src, Q_src_noJO, S_src = decompose_local_matrix(compute_local_matrix(src), src)
        Q_corr = correction_quat * Q_src_noJO if correction_quat is not None else Q_src_noJO
        _set_trs_keys(tgt, T_src, _quat_to_euler(Q_corr, tgt), S_src, ft, requested)
    except Exception as ex:
        cmd.warning(f"Hybrid A transfer failed {src}->{tgt} @ {frame}: {ex}")


def apply_hybrid_transfer_worldJO(src, tgt, frame, frame_offset=0, attrs=None, correction_quat=None):
    """
    Hybrid B: World-space to local JO-stripped transfer with optional bind correction.
    Best for rigs with identical structure but differing ancestor offsets.
    """
    try:
        if not cmd.objExists(src) or not cmd.objExists(tgt):
            return
        requested = _normalize_requested(attrs)
        ft = frame + frame_offset
        q_src_world = get_world_quaternion(src)
        parent = cmd.listRelatives(tgt, p=True, f=True)
        q_local = get_world_quaternion(parent[0]).inverse() * q_src_world if parent else q_src_world
        q_noJO = strip_joint_orient(tgt).inverse() * q_local
        q_final = correction_quat * q_noJO if correction_quat is not None else q_noJO
        _set_rotation_keys(tgt, _quat_to_euler(q_final, tgt), ft, requested)
    except Exception as ex:
        cmd.warning(f"Hybrid B transfer failed {src}->{tgt} @ {frame}: {ex}")