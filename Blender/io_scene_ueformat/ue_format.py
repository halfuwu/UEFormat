import gzip
import io
import os
import struct
import time
from enum import IntEnum, auto

import bpy
import bpy_extras
import numpy as np
import zstandard as zstd
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    FloatProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import Scene
from mathutils import Matrix, Quaternion, Vector

# ---------- ADDON ---------- #

bl_info = {
    "name": "UE Format (.uemodel / .ueanim)",
    "author": "Half",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > UE Format",
    "category": "Import",
}


class UEFORMAT_PT_Panel(bpy.types.Panel):
    bl_category = "UE Format"
    bl_label = "UE Format"
    bl_region_type = 'UI'
    bl_space_type = 'VIEW_3D'

    def draw(self, context):
        UEFORMAT_PT_Panel.draw_general_options(self, context)
        UEFORMAT_PT_Panel.draw_model_options(self, context)
        UEFORMAT_PT_Panel.draw_anim_options(self, context)

    @staticmethod
    def draw_general_options(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text="General", icon="SETTINGS")
        box.row().prop(bpy.context.scene.uf_settings, "scale")

    @staticmethod
    def draw_model_options(self, context, import_menu=False):
        layout = self.layout

        box = layout.box()
        box.label(text="Model", icon="OUTLINER_OB_MESH")
        box.row().prop(bpy.context.scene.uf_settings, "import_lods")
        box.row().prop(bpy.context.scene.uf_settings, "import_collision")
        box.row().prop(bpy.context.scene.uf_settings, "import_morph_targets")
        box.row().prop(bpy.context.scene.uf_settings, "import_sockets")
        box.row().prop(bpy.context.scene.uf_settings, "import_virtual_bones")
        box.row().prop(bpy.context.scene.uf_settings, "reorient_bones")
        box.row().prop(bpy.context.scene.uf_settings, "bone_length")

        if not import_menu:
            box.row().operator("uf.import_uemodel", icon='MESH_DATA')

    @staticmethod
    def draw_anim_options(self, context, import_menu=False):
        layout = self.layout

        box = layout.box()
        box.label(text="Animation", icon="ACTION")
        box.row().prop(bpy.context.scene.uf_settings, "rotation_only")

        if not import_menu:
            box.row().operator("uf.import_ueanim", icon='ANIM')


class UFImportUEModel(bpy.types.Operator, bpy_extras.io_utils.ImportHelper):
    bl_idname = "uf.import_uemodel"
    bl_label = "Import Model"
    bl_context = 'scene'

    filename_ext = ".uemodel"
    filter_glob: StringProperty(default="*.uemodel", options={'HIDDEN'}, maxlen=255)
    files: CollectionProperty(type=bpy.types.OperatorFileListElement, options={'HIDDEN', 'SKIP_SAVE'})
    directory: StringProperty(subtype='DIR_PATH')

    def execute(self, context):
        options = UEModelOptions(scale_factor=bpy.context.scene.uf_settings.scale,
                                 bone_length=bpy.context.scene.uf_settings.bone_length,
                                 reorient_bones=bpy.context.scene.uf_settings.reorient_bones,
                                 import_collision=bpy.context.scene.uf_settings.import_collision,
                                 import_sockets=bpy.context.scene.uf_settings.import_sockets,
                                 import_morph_targets=bpy.context.scene.uf_settings.import_morph_targets,
                                 import_lods=bpy.context.scene.uf_settings.import_lods,
                                 import_virtual_bones=bpy.context.scene.uf_settings.import_virtual_bones)
        for file in self.files:
            UEFormatImport(options).import_file(os.path.join(self.directory, file.name))
        return {'FINISHED'}

    def draw(self, context):
        UEFORMAT_PT_Panel.draw_general_options(self, context)
        UEFORMAT_PT_Panel.draw_model_options(self, context, True)


class UFImportUEAnim(bpy.types.Operator, bpy_extras.io_utils.ImportHelper):
    bl_idname = "uf.import_ueanim"
    bl_label = "Import Animation"
    bl_context = 'scene'

    filename_ext = ".ueanim"
    filter_glob: StringProperty(default="*.ueanim", options={'HIDDEN'}, maxlen=255)
    files: CollectionProperty(type=bpy.types.OperatorFileListElement, options={'HIDDEN', 'SKIP_SAVE'})
    directory: StringProperty(subtype='DIR_PATH')

    def execute(self, context):
        options = UEAnimOptions(scale_factor=bpy.context.scene.uf_settings.scale,
                               rotation_only=bpy.context.scene.uf_settings.rotation_only)
        for file in self.files:
            UEFormatImport(options).import_file(os.path.join(self.directory, file.name))
        return {'FINISHED'}

    def draw(self, context):
        UEFORMAT_PT_Panel.draw_general_options(self, context)
        UEFORMAT_PT_Panel.draw_anim_options(self, context, True)

class UFSettings(bpy.types.PropertyGroup):
    scale: FloatProperty(name="Scale", default=0.01, min=0.01)
    bone_length: FloatProperty(name="Bone Length", default=5, min=0.1)
    reorient_bones: BoolProperty(name="Reorient Bones", default=False)
    import_lods: BoolProperty(name="Import Levels of Detail", default=False)
    import_collision: BoolProperty(name="Import Collision", default=False)
    import_morph_targets: BoolProperty(name="Import Morph Targets", default=True)
    import_sockets: BoolProperty(name="Import Sockets", default=True)
    import_virtual_bones: BoolProperty(name="Import Virtual Bones", default=False)
    rotation_only: BoolProperty(name="Rotation Only", default=False)


def draw_import_menu(self, context):
    self.layout.operator(UFImportUEModel.bl_idname, text="Unreal Model (.uemodel)")
    self.layout.operator(UFImportUEAnim.bl_idname, text="Unreal Animation (.ueanim)")


operators = [UEFORMAT_PT_Panel, UFImportUEModel, UFImportUEAnim, UFSettings]


def register():
    global zstd_decompressor
    zstd_decompressor = zstd.ZstdDecompressor()


    # if used as script decomresser can be initialized like this
    # from . import ue_format
    # ue_format.zstd_decompressor = zstd.ZstdDecompressor()


    for operator in operators:
        bpy.utils.register_class(operator)

    Scene.uf_settings = PointerProperty(type=UFSettings)
    bpy.types.TOPBAR_MT_file_import.append(draw_import_menu)


def unregister():
    for operator in operators:
        bpy.utils.unregister_class(operator)

    del Scene.uf_settings
    bpy.types.TOPBAR_MT_file_import.remove(draw_import_menu)

    global zstd_decompressor
    del zstd_decompressor


if __name__ == "__main__":
    register()


# ---------- IMPORT CLASSES ---------- #

def bytes_to_str(in_bytes):
    return in_bytes.rstrip(b'\x00').decode()

def make_axis_vector(vec_in):
    vec_out = Vector()
    x, y, z = vec_in
    if abs(x) > abs(y):
        if abs(x) > abs(z):
            vec_out.x = 1 if x >= 0 else -1
        else:
            vec_out.z = 1 if z >= 0 else -1
    else:
        if abs(y) > abs(z):
            vec_out.y = 1 if y >= 0 else -1
        else:
            vec_out.z = 1 if z >= 0 else -1

    return vec_out


def get_case_insensitive(source, string):
    for item in source:
        if item.name.lower() == string.lower():
            return item


def get_active_armature():
    obj = bpy.context.object
    if obj is None:
        return

    if obj.type == "ARMATURE":
        return obj
    elif obj.type == "MESH":
        for modifier in obj.modifiers:
            if modifier.type == "ARMATURE":
                return modifier.object


class Log:
    INFO = u"\u001b[36m"
    WARN = u"\u001b[33m"
    ERROR = u"\u001b[31m"
    RESET = u"\u001b[0m"

    NoLog = False

    @staticmethod
    def info(message):
        if Log.NoLog: return
        print(f"{Log.INFO}[UEFORMAT] {Log.RESET}{message}")
        
    @staticmethod
    def warn(message):
        if Log.NoLog: return
        print(f"{Log.WARN}[UEFORMAT] {Log.RESET}{message}")

    @staticmethod
    def error(message):
        if Log.NoLog: return
        print(f"{Log.ERROR}[UEFORMAT] {Log.RESET}{message}")

    timers = {}

    @staticmethod
    def time_start(name):
        if Log.NoLog: return
        Log.timers[name] = time.time()
    
    @staticmethod
    def time_end(name):
        if Log.NoLog: return
        if name in Log.timers:
            Log.info(f"{name} took {time.time() - Log.timers[name]} seconds")
            del Log.timers[name]
        else:
            Log.error(f"Timer {name} does not exist")

class FArchiveReader:
    data = None
    size = 0

    def __init__(self, data):
        self.data = io.BytesIO(data)
        self.size = len(data)
        self.data.seek(0)

    def __enter__(self):
        # self.size = len(self.data.read())
        self.data.seek(0)
        return self

    def __exit__(self, type, value, traceback):
        self.data.close()

    def eof(self):
        return self.data.tell() >= self.size

    def read(self, size: int):
        return self.data.read(size)

    def read_to_end(self):
        return self.data.read(self.size - self.data.tell())

    def read_bool(self):
        return struct.unpack("?", self.data.read(1))[0]

    def read_string(self, size: int):
        string = self.data.read(size)
        return bytes_to_str(string)

    def read_fstring(self):
        size, = struct.unpack("i", self.data.read(4))
        string = self.data.read(size)
        return bytes_to_str(string)

    def read_int(self):
        return struct.unpack("i", self.data.read(4))[0]

    def read_int_vector(self, size: int):
        return struct.unpack(str(size) + "I", self.data.read(size * 4))

    def read_short(self):
        return struct.unpack("h", self.data.read(2))[0]

    def read_byte(self):
        return struct.unpack("c", self.data.read(1))[0]

    def read_float(self):
        return struct.unpack("f", self.data.read(4))[0]

    def read_float_vector(self, size: int):
        return struct.unpack(str(size) + "f", self.data.read(size * 4))

    def read_byte_vector(self, size: int):
        return struct.unpack(str(size) + "B", self.data.read(size))

    def skip(self, size: int):
        self.data.seek(size, 1)

    def read_bulk_array(self, predicate):
        count = self.read_int()
        return self.read_array(count, predicate)

    def read_array(self, count, predicate):
        array = []
        for counter in range(count):
            array.append(predicate(self))
        return array
    
    def chunk(self, size):
        return FArchiveReader(self.read(size))


MAGIC = "UEFORMAT"
MODEL_IDENTIFIER = "UEMODEL"
ANIM_IDENTIFIER = "UEANIM"

class EUEFormatVersion(IntEnum):
    BeforeCustomVersionWasAdded = 0
    SerializeBinormalSign = 1
    AddMultipleVertexColors = 2
    AddConvexCollisionGeom = 3
    LevelOfDetailFormatRestructure = 4
    SerializeVirtualBones = 5

    VersionPlusOne = auto()
    LatestVersion = VersionPlusOne - 1

class UEFormatOptions:
    pass

class UEModelOptions(UEFormatOptions):

    def __init__(self, link=True, scale_factor=0.01, bone_length=4.0, reorient_bones=False, import_collision=False, import_sockets=True, import_morph_targets=True, import_lods=False, import_virtual_bones=False):
        self.scale_factor = scale_factor
        self.bone_length = bone_length
        self.reorient_bones = reorient_bones
        self.link = link
        self.import_collision = import_collision
        self.import_sockets = import_sockets
        self.import_morph_targets = import_morph_targets
        self.import_lods = import_lods
        self.import_virtual_bones = import_virtual_bones


class UEAnimOptions(UEFormatOptions):

    def __init__(self, link=True, override_skeleton=None, scale_factor=0.01, rotation_only=False):
        self.override_skeleton = override_skeleton
        self.scale_factor = scale_factor
        self.rotation_only = rotation_only
        self.link = link

class UEFormatImport:

    def __init__(self, options=UEFormatOptions()):
        self.options = options

    def import_file(self, path: str):
        Log.time_start(f"Import {path}")
        with open(path, 'rb') as file:
            obj = self.import_data(file.read())
        Log.time_end(f"Import {path}")
        return obj

    def import_data(self, data):
        with FArchiveReader(data) as ar:
            magic = ar.read_string(len(MAGIC))
            if magic != MAGIC:
                return

            identifier = ar.read_fstring()
            self.file_version = EUEFormatVersion(int.from_bytes(ar.read_byte(), byteorder="big"))
            if self.file_version > EUEFormatVersion.LatestVersion:
                Log.error(f"File Version {self.file_version} is not supported for this version of the importer.")
                return
            object_name = ar.read_fstring()
            Log.info(f"Importing {object_name}")

            read_archive = ar
            is_compressed = ar.read_bool()
            if is_compressed:
                compression_type = ar.read_fstring()
                uncompressed_size = ar.read_int()
                compressed_size = ar.read_int()

                if compression_type == "GZIP":
                    read_archive = FArchiveReader(gzip.decompress(ar.read_to_end()))
                elif compression_type == "ZSTD":
                    read_archive = FArchiveReader(zstd_decompressor.decompress(ar.read_to_end(), uncompressed_size))
                else:
                    Log.error(f"Unknown Compression Type: {compression_type}")
                    return

            if identifier == MODEL_IDENTIFIER:
                return self.import_uemodel_data(read_archive, object_name)

            elif identifier == ANIM_IDENTIFIER:
                return self.import_ueanim_data(read_archive, object_name)

    # TODO clean up code quality, esp in the skeleton department
    def import_uemodel_data(self, ar: FArchiveReader, name: str):
        if self.file_version >= EUEFormatVersion.LevelOfDetailFormatRestructure:
            data = self.deserialize_model(ar)
        else:
            data = self.deserialize_model_legacy(ar)

        # meshes
        created_lods = []
        for index, lod in enumerate(data.lods):
            lod_name = f"{name}_{lod.name}"
            mesh_data = bpy.data.meshes.new(lod_name)
            
            mesh_data.from_pydata(lod.vertices, [], lod.indices)
    
            mesh_object = bpy.data.objects.new(lod_name, mesh_data)
            return_object = mesh_object
            if self.options.link:
                bpy.context.collection.objects.link(mesh_object)
    
            # normals
            if len(lod.normals) > 0:
                mesh_data.polygons.foreach_set("use_smooth", [True] * len(mesh_data.polygons))
                mesh_data.normals_split_custom_set_from_vertices(lod.normals)
                if bpy.app.version < (4, 1, 0):
                    mesh_data.use_auto_smooth = True

            # weights
            if len(lod.weights) > 0 and data.skeleton is not None and len(data.skeleton.bones) > 0:
                for weight in lod.weights:
                    bone_name = data.skeleton.bones[weight.bone_index].name
                    vertex_group = mesh_object.vertex_groups.get(bone_name)
                    if not vertex_group:
                        vertex_group = mesh_object.vertex_groups.new(name=bone_name)
                    vertex_group.add([weight.vertex_index], weight.weight, 'ADD')
    
            # morph targets
            if self.options.import_morph_targets and len(lod.morphs) > 0:
                default_key = mesh_object.shape_key_add(from_mix=False)
                default_key.name = "Default"
                default_key.interpolation = 'KEY_LINEAR'
    
                for morph in lod.morphs:
                    key = mesh_object.shape_key_add(from_mix=False)
                    key.name = morph.name
                    key.interpolation = 'KEY_LINEAR'
    
                    for delta in morph.deltas:
                        key.data[delta.vertex_index].co += Vector(delta.position)
            
            squish = lambda array: array.reshape(array.size) # Squish nD array into 1D array (required by foreach_set).
            do_remapping = lambda array, indices: array[indices]

            vertices = [vertex for polygon in mesh_data.polygons for vertex in polygon.vertices]
            # indices = np.array([index for polygon in mesh_data.polygons for index in polygon.loop_indices], dtype=np.int32)
            # assert np.all(indices[:-1] <= indices[1:]) # check if indices are sorted hmm idk
            for color_info in lod.colors:
                remapped = do_remapping(color_info.data, vertices)
                vertex_color = mesh_data.color_attributes.new(domain='CORNER', type='BYTE_COLOR', name=color_info.name)
                vertex_color.data.foreach_set("color", squish(remapped))

            for index, uvs in enumerate(lod.uvs):
                remapped = do_remapping(uvs, vertices)
                uv_layer = mesh_data.uv_layers.new(name="UV" + str(index))
                uv_layer.data.foreach_set("uv", squish(remapped))

            # materials
            if len(lod.materials) > 0:
                for i, material in enumerate(lod.materials):
                    mat = bpy.data.materials.get(material.material_name)
                    if mat is None:
                        mat = bpy.data.materials.new(name=material.material_name)
                    mesh_data.materials.append(mat)
    
                    start_face_index = (material.first_index // 3)
                    end_face_index = start_face_index + material.num_faces
                    for face_index in range(start_face_index, end_face_index):
                        mesh_data.polygons[face_index].material_index = i
                        
            created_lods.append(mesh_object)
            
            if not self.options.import_lods:
                break

        # skeleton
        if data.skeleton is not None and (len(data.skeleton.bones) > 0 or (self.options.import_sockets and len(data.skeleton.sockets) > 0)):
            armature_data = bpy.data.armatures.new(name=name)
            armature_data.display_type = 'STICK'
            
            template_armature_object = bpy.data.objects.new(name + "_Template_Skeleton", armature_data)
            template_armature_object.show_in_front = True
            bpy.context.collection.objects.link(template_armature_object)
            bpy.context.view_layer.objects.active = template_armature_object
            template_armature_object.select_set(True)

            if len(data.skeleton.bones) > 0:
                # create bones
                bpy.ops.object.mode_set(mode='EDIT')
                edit_bones = armature_data.edit_bones
                for bone in data.skeleton.bones:
                    bone_pos = Vector(bone.position)
                    bone_rot = Quaternion((bone.rotation[3], bone.rotation[0], bone.rotation[1], bone.rotation[2]))  # xyzw -> wxyz
        
                    edit_bone = edit_bones.new(bone.name)
                    edit_bone["orig_loc"] = bone_pos
                    edit_bone["orig_quat"] = bone_rot.conjugated() # todo unravel all these conjugations wtf, it works so imma leave it but jfc it's awful
                    edit_bone.length = self.options.bone_length * self.options.scale_factor
        
                    bone_matrix = Matrix.Translation(bone_pos) @ bone_rot.to_matrix().to_4x4()
        
                    if bone.parent_index >= 0:
                        parent_bone = edit_bones.get(data.skeleton.bones[bone.parent_index].name)
                        edit_bone.parent = parent_bone
                        bone_matrix = parent_bone.matrix @ bone_matrix
        
                    edit_bone.matrix = bone_matrix
                    
                    if not self.options.reorient_bones:
                        edit_bone["post_quat"] = bone_rot
        
                bpy.ops.object.mode_set(mode='OBJECT')
        
            # sockets
            if self.options.import_sockets and len(data.skeleton.sockets) > 0:
                # create sockets
                bpy.ops.object.mode_set(mode='EDIT')
                socket_collection = armature_data.collections.new("Sockets")
                for socket in data.skeleton.sockets:
                    socket_bone = edit_bones.new(socket.name)
                    socket_collection.assign(socket_bone)
                    socket_bone["is_socket"] = True
                    parent_bone = get_case_insensitive(edit_bones, socket.parent_name)
                    if parent_bone is None:
                        continue
                    socket_bone.parent = parent_bone
                    socket_bone.length = self.options.bone_length * self.options.scale_factor
                    socket_bone.matrix = parent_bone.matrix @ Matrix.Translation(socket.position) @ Quaternion((socket.rotation[3],socket.rotation[0],socket.rotation[1],socket.rotation[2])).to_matrix().to_4x4()  # xyzw -> wxyz
        
                bpy.ops.object.mode_set(mode='OBJECT')
        
            if len(data.skeleton.bones) > 0 and self.options.reorient_bones:
                bpy.ops.object.mode_set(mode='EDIT')
        
                for bone in edit_bones:
                    if bone.get("is_socket"):
                        continue
        
                    children = []
                    for child in bone.children:
                        if child.get("is_socket"):
                            continue
        
                        children.append(child)
        
                    if len(children) == 0 and bone.parent is None:
                        continue
        
                    target_length = bone.length
                    if len(children) == 0:
                        new_rot = Vector(bone.parent["reorient_direction"])
                        new_rot.rotate(Quaternion(bone["orig_quat"]).conjugated())
        
                        target_rotation = make_axis_vector(new_rot)
                    else:
                        avg_child_pos = Vector()
                        avg_child_length = 0
                        for child in children:
                            pos = Vector(child["orig_loc"])
                            avg_child_pos += pos
                            avg_child_length += pos.length
        
                        avg_child_pos /= len(children)
                        avg_child_length /= len(children)
        
                        target_rotation = make_axis_vector(avg_child_pos)
                        bone["reorient_direction"] = target_rotation
        
                        target_length = avg_child_length
        
                    post_quat = Vector((0, 1, 0)).rotation_difference(target_rotation)
                    bone.matrix @= post_quat.to_matrix().to_4x4()
                    bone.length = max(0.01, target_length)
        
                    post_quat.rotate(Quaternion(bone["orig_quat"]).conjugated())
                    bone["post_quat"] = post_quat
        
        
                bpy.ops.object.mode_set(mode='OBJECT')

            
            if len(created_lods) > 0:
                bpy.data.objects.remove(template_armature_object)
            else:
                template_armature_object.name = name
                return_object = template_armature_object

                # this is the same functionality as in unreal dont @ me
                if self.options.import_virtual_bones:
                    bpy.ops.object.mode_set(mode='EDIT')
                    virtual_bone_collection = armature_data.collections.new("Virtual Bones")
                    edit_bones = armature_data.edit_bones
                    for virtual in data.skeleton.virtual_bones:
                        source_bone = edit_bones.get(virtual.source_name)
                        if source_bone is None:
                            continue
                            
                        virtual_bone = edit_bones.new(virtual.virtual_name)
                        virtual_bone_collection.assign(virtual_bone)
                        virtual_bone.head = source_bone.tail
                        virtual_bone.tail = source_bone.head
        
                    bpy.ops.object.mode_set(mode='POSE')
        
                    for virtual in data.skeleton.virtual_bones:
                        virtual_bone = template_armature_object.pose.bones.get(virtual.virtual_name)
                        if virtual_bone is None:
                            continue
                            
                        constraint = virtual_bone.constraints.new("IK")
                        constraint.target = template_armature_object
                        constraint.subtarget = virtual.target_name
                        constraint.chain_count = 1
                        virtual_bone.ik_stretch = 1
        
                    bpy.ops.object.mode_set(mode='OBJECT')

                # bone colors
                for bone in template_armature_object.pose.bones:
                    if len(bone.children) == 0:
                        bone.color.palette = 'THEME03'

                # socket colors
                for socket in data.skeleton.sockets:
                    socket_bone = template_armature_object.pose.bones.get(socket.name)
                    if socket_bone is not None:
                        socket_bone.color.palette = 'THEME05'

                # virtual bone colors
                for virtual in data.skeleton.virtual_bones:
                    virtual_bone = template_armature_object.pose.bones.get(virtual.virtual_name)
                    if virtual_bone is not None:
                        virtual_bone.color.palette = 'THEME11'
            
            for lod in created_lods:
                armature_object = bpy.data.objects.new(lod.name + "_Skeleton", armature_data)
                armature_object.show_in_front = True
                return_object = armature_object
            
                if self.options.link:
                    bpy.context.collection.objects.link(armature_object)
                bpy.context.view_layer.objects.active = armature_object
                armature_object.select_set(True)
            
                lod.parent = armature_object
                
                # armature modifier
                armature_modifier = lod.modifiers.new(armature_object.name, type='ARMATURE')
                armature_modifier.show_expanded = False
                armature_modifier.use_vertex_groups = True
                armature_modifier.object = armature_object
            
                bpy.ops.object.mode_set(mode='POSE')
                
                # bone colors
                for bone in armature_object.pose.bones:
                    if lod.vertex_groups.get(bone.name) is None:
                        bone.color.palette = 'THEME14'
                        continue
            
                    if len(bone.children) == 0:
                        bone.color.palette = 'THEME03'
                        
                # socket colors
                for socket in data.skeleton.sockets:
                    socket_bone = armature_object.pose.bones.get(socket.name)
                    if socket_bone is not None:
                        socket_bone.color.palette = 'THEME05'

                # virtual bone colors
                for virtual in data.skeleton.virtual_bones:
                    virtual_bone = armature_object.pose.bones.get(virtual.virtual_name)
                    if virtual_bone is not None:
                        virtual_bone.color.palette = 'THEME11'
                        
                bpy.ops.object.mode_set(mode='OBJECT')

        # collision
        if self.options.import_collision and len(data.collisions) > 0:
            for index, collision in enumerate(data.collisions):
                collision_name = index if collision.name == "None" else collision.name
                collision_object_name = name + f"_Collision_{collision_name}"
                collision_mesh_data = bpy.data.meshes.new(collision_object_name)
                collision_mesh_data.from_pydata(collision.vertices, [], collision.indices)

                collision_mesh_object = bpy.data.objects.new(collision_object_name, collision_mesh_data)
                collision_mesh_object.display_type = 'WIRE'
                if self.options.link:
                    bpy.context.collection.objects.link(collision_mesh_object)

        return return_object

    def import_ueanim_data(self, ar: FArchiveReader, name: str):
        data = UEAnim()

        data.num_frames = ar.read_int()
        data.frames_per_second = ar.read_float()

        while not ar.eof():
            header_name = ar.read_fstring()
            array_size = ar.read_int()
            byte_size = ar.read_int()

            if header_name == "TRACKS":
                data.tracks = ar.read_array(array_size, lambda ar: Track(ar, self.options.scale_factor))
            elif header_name == "CURVES":
                data.curves = ar.read_array(array_size, lambda ar: Curve(ar))
            else:
                ar.skip(byte_size)

        action = bpy.data.actions.new(name=name)

        armature = self.options.override_skeleton or get_active_armature()
        if self.options.link:
            armature.animation_data_create()
            armature.animation_data.action = action

        # bone anim data
        pose_bones = armature.pose.bones
        for track in data.tracks:
            bone = get_case_insensitive(pose_bones, track.name)
            if bone is None:
                continue

            def create_fcurves(name, count, key_count):
                path = bone.path_from_id(name)
                curves = []
                for i in range(count):
                    curve = action.fcurves.new(path, index=i)
                    curve.keyframe_points.add(key_count)
                    curves.append(curve)
                return curves

            def add_key(curves, vector, key_index, frame):
                for i in range(len(vector)):
                    curves[i].keyframe_points[key_index].co = frame, vector[i]
                    curves[i].keyframe_points[key_index].interpolation = "LINEAR"
                    
            orig_loc = Vector(orig_loc) if (orig_loc := bone.bone.get("orig_loc")) else Vector()
            orig_quat = Quaternion(orig_quat) if (orig_quat := bone.bone.get("orig_quat")) else Quaternion()
            post_quat = Quaternion(post_quat) if (post_quat := bone.bone.get("post_quat")) else Quaternion()

            if not self.options.rotation_only:
                loc_curves = create_fcurves("location", 3, len(track.position_keys))
                scale_curves = create_fcurves("scale", 3, len(track.scale_keys))
                for index, key in enumerate(track.position_keys):
                    pos = key.get_vector()
                    pos -= orig_loc
                    pos.rotate(post_quat.conjugated())

                    add_key(loc_curves, pos, index, key.frame)

                for index, key in enumerate(track.scale_keys):
                    add_key(scale_curves, key.value, index, key.frame)

            rot_curves = create_fcurves("rotation_quaternion", 4, len(track.rotation_keys))
            for index, key in enumerate(track.rotation_keys):
                p_quat = key.get_quat().conjugated()

                q = post_quat.copy()
                q.rotate( orig_quat )

                quat = q

                q = post_quat.copy()

                if bone.parent == None:
                    q.rotate( p_quat.conjugated() )
                else:
                    q.rotate( p_quat )

                quat.rotate( q.conjugated() )

                add_key(rot_curves, quat, index, key.frame)

            bone.matrix_basis.identity()

        return action

    def deserialize_model(self, ar: FArchiveReader):
        data = UEModel()
        while not ar.eof():
            section_name = ar.read_fstring()
            array_size = ar.read_int()
            byte_size = ar.read_int()

            if section_name == "LODS":
                data.lods = []
                for i in range(array_size):
                    lod_name = ar.read_fstring()
                    lod_size = ar.read_int()
                    lod = UEModelLOD(ar.chunk(lod_size), lod_name, self.options.scale_factor)
                    data.lods.append(lod)
            elif section_name == "SKELETON":
                data.skeleton = UEModelSkeleton(ar.chunk(byte_size), self.options.scale_factor)
            elif section_name == "COLLISION":
                data.collisions = ar.read_array(array_size, lambda ar: ConvexCollision(ar, self.options.scale_factor))
            else:
                Log.warn(f"Unknown Section Data: {section_name}")
                ar.skip(byte_size)
        return data

    def deserialize_model_legacy(self, ar: FArchiveReader):
        data = UEModel()
        data.skeleton = UEModelSkeleton()
        lod = UEModelLOD()
        lod.name = "LOD0"
        while not ar.eof():
            header_name = ar.read_fstring()
            array_size = ar.read_int()
            byte_size = ar.read_int()
    
            pos = ar.data.tell()
            if header_name == "VERTICES":
                flattened = ar.read_float_vector(array_size * 3)
                lod.vertices = (np.array(flattened) * self.options.scale_factor).reshape(array_size, 3)
            elif header_name == "INDICES":
                lod.indices = np.array(ar.read_int_vector(array_size), dtype=np.int32).reshape(array_size // 3, 3)
            elif header_name == "NORMALS":
                if self.file_version >= EUEFormatVersion.SerializeBinormalSign:
                    flattened = np.array(ar.read_float_vector(array_size * 4)) # W XYZ # TODO: change to XYZ W
                    lod.normals = flattened.reshape(-1,4)[:,1:]
                else:
                    flattened = np.array(ar.read_float_vector(array_size * 3)).reshape(array_size, 3)
                    lod.normals = flattened
            elif header_name == "TANGENTS":
                ar.skip(array_size * 3 * 3)
                # flattened = np.array(ar.read_float_vector(array_size * 3)).reshape(array_size, 3)
            elif header_name == "VERTEXCOLORS":
                if self.file_version >= EUEFormatVersion.AddMultipleVertexColors:
                    lod.colors = []
                    for i in range(array_size):
                        lod.colors.append(VertexColor.read(ar))
                else:
                    lod.colors = [VertexColor("COL0", (np.array(ar.read_byte_vector(array_size * 4)).reshape(array_size, 4) / 255).astype(np.float32))]
            elif header_name == "TEXCOORDS":
                lod.uvs = []
                for i in range(array_size):
                    count = ar.read_int()
                    lod.uvs.append(np.array(ar.read_float_vector(count * 2)).reshape(count, 2))
            elif header_name == "MATERIALS":
                lod.materials = ar.read_array(array_size, lambda ar: Material(ar))
            elif header_name == "WEIGHTS":
                lod.weights = ar.read_array(array_size, lambda ar: Weight(ar))
            elif header_name == "MORPHTARGETS":
                lod.morphs = ar.read_array(array_size, lambda ar: MorphTarget(ar, self.options.scale_factor))
            elif header_name == "BONES":
                data.skeleton.bones = ar.read_array(array_size, lambda ar: Bone(ar, self.options.scale_factor))
            elif header_name == "SOCKETS":
                data.skeleton.sockets = ar.read_array(array_size, lambda ar: Socket(ar, self.options.scale_factor))
            elif header_name == "COLLISION" and self.file_version >= EUEFormatVersion.AddConvexCollisionGeom:
                data.collisions = ar.read_array(array_size, lambda ar: ConvexCollision(ar, self.options.scale_factor))
            else:
                Log.warn(f"Unknown Data: {header_name}")
                ar.skip(byte_size)
            ar.data.seek(pos + byte_size, 0)
            
        data.lods.append(lod)
        
        return data


class UEModel:
    lods = []
    collisions = []
    skeleton = None
    #physics = None

class UEModelLOD:
    name = ""
    vertices = []
    indices = []
    normals = []
    tangents = []
    colors = []
    uvs = []
    materials = []
    morphs = []
    weights = []

    def __init__(self, ar: FArchiveReader = None, name = "", scale = 1.0):
        if ar is None:
            return

        self.name = name
        while not ar.eof():
            header_name = ar.read_fstring()
            array_size = ar.read_int()
            byte_size = ar.read_int()

            pos = ar.data.tell()
            if header_name == "VERTICES":
                flattened = ar.read_float_vector(array_size * 3)
                self.vertices = (np.array(flattened) * scale).reshape(array_size, 3)
            elif header_name == "INDICES":
                self.indices = np.array(ar.read_int_vector(array_size), dtype=np.int32).reshape(array_size // 3, 3)
            elif header_name == "NORMALS":
                flattened = np.array(ar.read_float_vector(array_size * 4)) # W XYZ # TODO: change to XYZ W
                self.normals = flattened.reshape(-1,4)[:,1:]
            elif header_name == "TANGENTS":
                ar.skip(array_size * 3 * 3)
            elif header_name == "VERTEXCOLORS":
                self.colors = []
                for i in range(array_size):
                    self.colors.append(VertexColor.read(ar))
            elif header_name == "TEXCOORDS":
                self.uvs = []
                for i in range(array_size):
                    count = ar.read_int()
                    self.uvs.append(np.array(ar.read_float_vector(count * 2)).reshape(count, 2))
            elif header_name == "MATERIALS":
                self.materials = ar.read_array(array_size, lambda ar: Material(ar))
            elif header_name == "WEIGHTS":
                self.weights = ar.read_array(array_size, lambda ar: Weight(ar))
            elif header_name == "MORPHTARGETS":
                self.morphs = ar.read_array(array_size, lambda ar: MorphTarget(ar, scale))
            else:
                Log.warn(f"Unknown Mesh Data: {header_name}")
                ar.skip(byte_size)
            ar.data.seek(pos + byte_size, 0)

class UEModelSkeleton:
    bones = []
    sockets = []
    virtual_bones = []

    def __init__(self, ar: FArchiveReader = None, scale = 1.0):
        if ar is None:
            return

        while not ar.eof():
            header_name = ar.read_fstring()
            array_size = ar.read_int()
            byte_size = ar.read_int()

            pos = ar.data.tell()
            if header_name == "BONES":
                self.bones = ar.read_array(array_size, lambda ar: Bone(ar, scale))
            elif header_name == "SOCKETS":
                self.sockets = ar.read_array(array_size, lambda ar: Socket(ar, scale))
            elif header_name == "VIRTUALBONES":
                self.virtual_bones = ar.read_array(array_size, lambda ar: VirtualBone(ar))
            else:
                Log.warn(f"Unknown Skeleton Data: {header_name}")
                ar.skip(byte_size)
            ar.data.seek(pos + byte_size, 0)

'''class UEModelPhysics:
    bodies = []

    def __init__(self, ar: FArchiveReader, scale):

        while not ar.eof():
            header_name = ar.read_fstring()
            array_size = ar.read_int()
            byte_size = ar.read_int()

            pos = ar.data.tell()
            if header_name == "BODIES":
                self.bodies = ar.read_array(array_size, lambda ar: BodySetup(ar, scale))
            else:
                Log.warn(f"Unknown Skeleton Data: {header_name}")
                ar.skip(byte_size)
            ar.data.seek(pos + byte_size, 0)

class EPhysicsType(IntEnum):
    PhysType_Default = 0
    PhysType_Kinematic = 1
    PhysType_Simulated = 2


class BodySetup:
    bone_name = ""
    physics_type = EPhysicsType.PhysType_Default
    
    sphere_elems = []
    box_elems = []
    capsule_elems = []
    tapered_capsule_elems = []
    convex_elems = []
    
    def __init__(self, ar: FArchiveReader, scale):
        self.bone_name = ar.read_fstring()
        self.physics_type = EPhysicsType(int.from_bytes(ar.read_byte(), byteorder="big"))
        
        self.sphere_elems = ar.read_bulk_array(lambda ar: SphereCollision(ar, scale))
        self.box_elems = ar.read_bulk_array(lambda ar: BoxCollision(ar, scale))
        self.capsule_elems = ar.read_bulk_array(lambda ar: CapsuleCollision(ar, scale))
        self.tapered_capsule_elems = ar.read_bulk_array(lambda ar: TaperedCapsuleCollision(ar, scale))
        self.convex_elems = ar.read_bulk_array(lambda ar: ConvexCollision(ar, scale))
        
class SphereCollision:
    name = ""
    center = []
    radius = 0

    def __init__(self, ar: FArchiveReader, scale):
        self.name = ar.read_fstring()
        self.center = [pos * scale for pos in ar.read_float_vector(3)]
        self.radius = ar.read_float()

class BoxCollision:
    name = ""
    center = []
    rotation = []
    x = 0
    y = 0
    z = 0

    def __init__(self, ar: FArchiveReader, scale):
        self.name = ar.read_fstring()
        self.center = [pos * scale for pos in ar.read_float_vector(3)]
        self.rotation = ar.read_float_vector(3)
        self.x = ar.read_float()
        self.y = ar.read_float()
        self.z = ar.read_float()

class CapsuleCollision:
    name = ""
    center = []
    rotation = []
    radius = 0
    length = 0

    def __init__(self, ar: FArchiveReader, scale):
        self.name = ar.read_fstring()
        self.center = [pos * scale for pos in ar.read_float_vector(3)]
        self.rotation = ar.read_float_vector(3)
        self.radius = ar.read_float()
        self.length = ar.read_float()

class TaperedCapsuleCollision:
    name = ""
    center = []
    rotation = []
    radius0 = 0
    radius1 = 0
    length = 0

    def __init__(self, ar: FArchiveReader, scale):
        self.name = ar.read_fstring()
        self.center = [pos * scale for pos in ar.read_float_vector(3)]
        self.rotation = ar.read_float_vector(3)
        self.radius0 = ar.read_float()
        self.radius1 = ar.read_float()
        self.length = ar.read_float()'''

class ConvexCollision:
    name = ""
    vertices = []
    indices = []

    def __init__(self, ar: FArchiveReader, scale):
        self.name = ar.read_fstring()

        vertices_count = ar.read_int()
        vertices_flattened = ar.read_float_vector(vertices_count * 3)
        self.vertices = (np.array(vertices_flattened) * scale).reshape(vertices_count, 3)

        indices_count = ar.read_int()
        self.indices = np.array(ar.read_int_vector(indices_count), dtype=np.int32).reshape(indices_count // 3, 3)


class VertexColor:
    name = ""
    data = []

    def __init__(self, name, data):
        self.name = name
        self.data = data

    @classmethod
    def read(cls, ar: FArchiveReader):
        name = ar.read_fstring()
        count = ar.read_int()
        data = (np.array(ar.read_byte_vector(count * 4)).reshape(count, 4) / 255).astype(np.float32)

        return cls(name, data)

class Material:
    material_name = ""
    first_index = -1
    num_faces = -1

    def __init__(self, ar: FArchiveReader):
        self.material_name = ar.read_fstring()
        self.first_index = ar.read_int()
        self.num_faces = ar.read_int()


class Bone:
    name = ""
    parent_index = -1
    position = []
    rotation = []

    def __init__(self, ar: FArchiveReader, scale):
        self.name = ar.read_fstring()
        self.parent_index = ar.read_int()
        self.position = [pos * scale for pos in ar.read_float_vector(3)]
        self.rotation = ar.read_float_vector(4)


class Weight:
    bone_index = -1
    vertex_index = -1
    weight = -1

    def __init__(self, ar: FArchiveReader):
        self.bone_index = ar.read_short()
        self.vertex_index = ar.read_int()
        self.weight = ar.read_float()


class MorphTarget:
    name = ""
    deltas = []

    def __init__(self, ar: FArchiveReader, scale):
        self.name = ar.read_fstring()

        self.deltas = ar.read_bulk_array(lambda ar: MorphTargetData(ar, scale))


class MorphTargetData:
    position = []
    normals = []
    vertex_index = -1

    def __init__(self, ar: FArchiveReader, scale):
        self.position = [pos * scale for pos in ar.read_float_vector(3)]
        self.normals = ar.read_float_vector(3)
        self.vertex_index = ar.read_int()


class Socket:
    name = ""
    parent_name = ""
    position = []
    rotation = []
    scale = []

    def __init__(self, ar: FArchiveReader, scale):
        self.name = ar.read_fstring()
        self.parent_name = ar.read_fstring()
        self.position = [pos * scale for pos in ar.read_float_vector(3)]
        self.rotation = ar.read_float_vector(4)
        self.scale = ar.read_float_vector(3)

class VirtualBone:
    source_name = ""
    target_name = ""
    virtual_name = ""

    def __init__(self, ar: FArchiveReader):
        self.source_name = ar.read_fstring()
        self.target_name = ar.read_fstring()
        self.virtual_name = ar.read_fstring()


class UEAnim:
    num_frames = 0
    frames_per_second = 0
    tracks = []
    curves = []


class Curve:
    name = ""
    keys = []

    def __init__(self, ar: FArchiveReader):
        self.name = ar.read_fstring()
        self.keys = ar.read_bulk_array(lambda ar: FloatKey(ar))


class Track:
    name = ""
    position_keys = []
    rotation_keys = []
    scale_keys = []

    def __init__(self, ar: FArchiveReader, scale):
        self.name = ar.read_fstring()
        self.position_keys = ar.read_bulk_array(lambda ar: VectorKey(ar, scale))
        self.rotation_keys = ar.read_bulk_array(lambda ar: QuatKey(ar))
        self.scale_keys = ar.read_bulk_array(lambda ar: VectorKey(ar))


class AnimKey:
    frame = -1

    def __init__(self, ar: FArchiveReader):
        self.frame = ar.read_int()


class VectorKey(AnimKey):
    value = []

    def __init__(self, ar: FArchiveReader, multiplier=1):
        super().__init__(ar)
        self.value = [float * multiplier for float in ar.read_float_vector(3)]

    def get_vector(self) -> Vector:
        return Vector(self.value)


class QuatKey(AnimKey):
    value = []

    def __init__(self, ar: FArchiveReader):
        super().__init__(ar)
        self.value = ar.read_float_vector(4)

    def get_quat(self) -> Quaternion:
        return Quaternion((self.value[3], self.value[0], self.value[1], self.value[2]))


class FloatKey(AnimKey):
    value = 0.0

    def __init__(self, ar: FArchiveReader):
        super().__init__(ar)
        self.value = ar.read_float()