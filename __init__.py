#!/usr/bin/env python
# SPDX-License-Identifier: GPL-3.0-only
#
# Copyright (C) 2023 Tayou <tayou@gmx.net>
#
# This file is part of the Blender Plugin "Bone and Vertex Group Merge" by Tayou.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; If not, see <https://www.gnu.org/licenses/>.

import bpy

bl_info = {
    "name": "Bone and Vertex Group Merge",
    "category": "Armature",
    "author": "Tayou",
    "location": "Armature > Context Menu > Merge Bones",
    "description": "Allows you to merge any amount of selected bones into the active bone, with respect to any meshes and their vertex groups.",
    "version": (1, 0, 0),
    "blender": (3, 4, 1),
    "tracker_url": 'https://github.com/TayouVR/Blender_merge-bones/issues',
    "doc_url": "https://github.com/TayouVR/Blender_merge-bones",
    "wiki_url": 'https://github.com/TayouVR/Blender_merge-bones',
    'warning': '',
}


# --------------------------------------------
# look at TODOs you idiot!
# --------------------------------------------

class MergeBones(bpy.types.Operator):
    """Merge Selected Bones into Active"""  # Use this as a tooltip for menu items and buttons.
    bl_idname = "armature.merge"  # Unique identifier for buttons and menu items to reference.
    bl_label = "Merge Bones"  # Display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}  # Enable undo for the operator.

    # Merge source into target
    def merge_vertex_groups(self, object, vertex_group_target, vertex_group_source):
        #create missing vertex group
        if (not (vertex_group_target in object.vertex_groups)):
            object.vertex_groups.new(name=vertex_group_target)

        # check if both exist
        if (vertex_group_target in object.vertex_groups and
                vertex_group_source in object.vertex_groups):

            # loop through vertecies
            for id, vert in enumerate(object.data.vertices):
                available_groups = [v_group_elem.group for v_group_elem in vert.groups]

                vertex_weight_S = vertex_weight_T = vertex_weight_SUM = 0;
                if object.vertex_groups[vertex_group_source].index in available_groups:
                    vertex_weight_S = object.vertex_groups[vertex_group_source].weight(id)
                if object.vertex_groups[vertex_group_target].index in available_groups:
                    vertex_weight_T = object.vertex_groups[vertex_group_target].weight(id)

                vertex_weight_SUM = vertex_weight_S + vertex_weight_T
                # only add to vertex group is weight is > 0
                if vertex_weight_SUM > 0:
                    object.vertex_groups[vertex_group_target].add([id], vertex_weight_SUM, 'REPLACE')

            # TODO test if this removes the vertex group
            object.vertex_groups.remove(object.vertex_groups[vertex_group_source])

    # find objects, which target the selected armature and merge vertex groups
    def find_objects_with_armature_and_merge(self, context):
        target_bone = context.active_bone
        for object in bpy.data.objects:
            for modifier in object.modifiers:
                if (isinstance(modifier, bpy.types.ArmatureModifier)):
                    if (modifier.object is context.active_object):
                        print("handling object: " + object.name)
                        for source_bone in bpy.context.selected_bones:
                            if (target_bone.name != source_bone.name):
                                print("merging " + source_bone.name + " into " + target_bone.name)
                                self.merge_vertex_groups(object, target_bone.name, source_bone.name)

    # delete bones
    def delete_bones(self):
        for source_bone in bpy.context.selected_bones:
            source_name = source_bone.name

            if (bpy.context.active_bone.name != source_bone.name):
                print("Deleting " + source_name + " Bone after weight merge")
                bpy.context.active_object.data.edit_bones.remove(source_bone)

    def execute(self, context):
        print("Starting Merge!!!")

        print("Disabling X mirror for armature edit mode")
        originalXmirrorSetting = context.active_object.data.use_mirror_x
        context.active_object.data.use_mirror_x = False;

        self.find_objects_with_armature_and_merge(context)
        self.delete_bones()

        print("Resetting X mirror setting for armature to before script state")
        context.active_object.data.use_mirror_x = originalXmirrorSetting;

        print("Merging Done!!!")
        return {'FINISHED'}  # Lets Blender know the operator finished successfully.


def draw_menu(self, context):
    layout = self.layout
    layout.separator()
    layout.operator(MergeBones.bl_idname)


def register():
    bpy.utils.register_class(MergeBones)
    bpy.types.VIEW3D_MT_armature_context_menu.append(draw_menu)


def unregister():
    bpy.utils.unregister_class(MergeBones)
    bpy.types.VIEW3D_MT_armature_context_menu.remove(draw_menu)


# This allows you to run the script directly from Blender's Text editor
# to test the add-on without having to install it.
if __name__ == "__main__":
    print("Test executing plugin, registering menu")
    register()
