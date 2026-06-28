#!/usr/bin/env python
# SPDX-License-Identifier: GPL-3.0-only
#
# Copyright (C) 2025 Tayou <git@tayou.org>
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
from bpy.props import EnumProperty

bl_info = {
    "name": "Bone and Vertex Group Merge",
    "category": "Armature",
    "author": "Tayou",
    "location": "Armature > Context Menu > Merge Bones",
    "description": "Allows you to merge any amount of selected bones into the active bone, with respect to any meshes and their vertex groups.",
    "version": (1, 4, 1),
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
    """Merge Selected Bones into Active"""
    bl_idname = "armature.merge"
    bl_label = "Merge Bones"
    bl_options = {'REGISTER', 'UNDO'}

    target_bone: EnumProperty(
        name="Target Bone",
        description="Choose how the merge target is selected",
        items=[
            ('FIRST_OF_CHAIN', "First of Chain", "Merge each selected chain into its own root bone"),
            ('ACTIVE', "Active", "Merge all selected bones into the active bone"),
        ],
        default='FIRST_OF_CHAIN',
    )

    merge_mode: EnumProperty(
        name="Merge Mode",
        description="Choose how the surviving bone is reshaped",
        items=[
            ('AUTO', "Auto", "Adjust end when possible, otherwise keep"),
            ('KEEP', "Keep", "Do not change the bone shape"),
            ('ADJUST_END', "Adjust End", "Move the tail to the end bone, or average end positions for branching"),
            ('FULL_AVERAGE', "Full Average", "Move both head and tail based on the selection"),
        ],
        default='AUTO',
    )

    # Merge source into target
    def merge_vertex_groups(self, object, vertex_group_target, vertex_group_source):
        if not (vertex_group_target in object.vertex_groups):
            object.vertex_groups.new(name=vertex_group_target)

        if (vertex_group_target in object.vertex_groups and
                vertex_group_source in object.vertex_groups):

            # Merges source vertex group weights into target; removes source
            for id, vert in enumerate(object.data.vertices):
                available_groups = [v_group_elem.group for v_group_elem in vert.groups]

                vertex_weight_S = vertex_weight_T = vertex_weight_SUM = 0
                if object.vertex_groups[vertex_group_source].index in available_groups:
                    vertex_weight_S = object.vertex_groups[vertex_group_source].weight(id)
                if object.vertex_groups[vertex_group_target].index in available_groups:
                    vertex_weight_T = object.vertex_groups[vertex_group_target].weight(id)

                vertex_weight_SUM = vertex_weight_S + vertex_weight_T
                if vertex_weight_SUM > 0:
                    object.vertex_groups[vertex_group_target].add([id], vertex_weight_SUM, 'REPLACE')

            object.vertex_groups.remove(object.vertex_groups[vertex_group_source])

    def analyze_component(self, component_bones):
        component_set = set(component_bones)

        roots = [bone for bone in component_bones if bone.parent not in component_set]
        leaves = [bone for bone in component_bones if not any(child in component_set for child in bone.children)]

        return {
            "bones": component_bones,
            "roots": roots,
            "leaves": leaves,
            "root_count": len(roots),
            "leaf_count": len(leaves),
        }

    def analyze_selection(self, selected_bones):
        selected_set = set(selected_bones)
        unvisited = set(selected_bones)
        components = []

        while unvisited:
            start = next(iter(unvisited))
            stack = [start]
            component = []

            while stack:
                bone = stack.pop()
                if bone in component:
                    continue

                component.append(bone)
                unvisited.discard(bone)

                if bone.parent in selected_set:
                    stack.append(bone.parent)

                for child in bone.children:
                    if child in selected_set:
                        stack.append(child)

            components.append(self.analyze_component(component))

        return {
            "components": components,
            "component_count": len(components),
        }

    def average_vector(self, vectors):
        if not vectors:
            return None

        total = vectors[0].copy()
        for vec in vectors[1:]:
            total += vec
        return total / len(vectors)

    def resolve_merge_mode(self):
        if self.merge_mode != 'AUTO':
            return self.merge_mode

        # AUTO merge mode:
        # ADJUST_END only for FIRST_OF_CHAIN, keep for legacy ACTIVE target
        if self.target_bone == 'FIRST_OF_CHAIN':
            return 'ADJUST_END'

        return 'KEEP'

    def get_component_target_bone(self, context, component_analysis):
        active_bone = context.active_bone
        if active_bone is None or not component_analysis["bones"]:
            return None

        if self.target_bone == 'ACTIVE':
            return active_bone

        # FIRST_OF_CHAIN
        return component_analysis["roots"][0] if component_analysis["roots"] else active_bone

    def get_selection_head_tail(self, target_bone, component_analysis, merge_mode):
        roots = component_analysis["roots"]
        leaves = component_analysis["leaves"]

        head = target_bone.head.copy()
        tail = target_bone.tail.copy()

        if merge_mode == 'KEEP':
            return head, tail

        if merge_mode == 'ADJUST_END':
            if leaves:
                averaged_tail = self.average_vector([bone.tail.copy() for bone in leaves])
                if averaged_tail is not None:
                    tail = averaged_tail
            return head, tail

        # FULL_AVERAGE
        if roots:
            averaged_head = self.average_vector([bone.head.copy() for bone in roots])
            if averaged_head is not None:
                head = averaged_head
        if leaves:
            averaged_tail = self.average_vector([bone.tail.copy() for bone in leaves])
            if averaged_tail is not None:
                tail = averaged_tail

        return head, tail

    def reshape_target_bone(self, target_bone, component_analysis, merge_mode):
        if target_bone is None:
            return

        head, tail = self.get_selection_head_tail(target_bone, component_analysis, merge_mode)

        if merge_mode == 'FULL_AVERAGE':
            target_bone.head = head
            target_bone.tail = tail
        elif merge_mode == 'ADJUST_END':
            target_bone.tail = tail

    def build_target_map(self, context, analysis):
        target_map = {}

        if self.target_bone == 'ACTIVE':
            target_bone = context.active_bone
            if target_bone is None:
                return target_map

            for component in analysis["components"]:
                for source_bone in component["bones"]:
                    target_map[source_bone] = target_bone

            return target_map

        # FIRST_OF_CHAIN: each component gets its own root target
        for component in analysis["components"]:
            target_bone = self.get_component_target_bone(context, component)
            if target_bone is None:
                continue

            for source_bone in component["bones"]:
                target_map[source_bone] = target_bone

        return target_map

    def merge_vertex_groups_for_target_map(self, context, target_map):
        for obj in bpy.data.objects:
            for modifier in obj.modifiers:
                if isinstance(modifier, bpy.types.ArmatureModifier) and modifier.object is context.active_object:
                    print("handling object: " + obj.name)
                    for source_bone, target_bone in target_map.items():
                        if source_bone != target_bone:
                            print("merging " + source_bone.name + " into " + target_bone.name)
                            self.merge_vertex_groups(obj, target_bone.name, source_bone.name)

    def delete_bones_for_target_map(self, context, target_map):
        armature = context.active_object.data

        for source_bone, target_bone in target_map.items():
            if source_bone != target_bone:
                print("Deleting " + source_bone.name + " Bone after weight merge")
                armature.edit_bones.remove(source_bone)

    def execute(self, context):
        print("Starting Merge!!!")

        print("Disabling X mirror for armature edit mode")
        originalXmirrorSetting = context.active_object.data.use_mirror_x
        context.active_object.data.use_mirror_x = False

        selected_bones = list(context.selected_bones)
        analysis = self.analyze_selection(selected_bones)
        target_map = self.build_target_map(context, analysis)
        merge_mode = self.resolve_merge_mode()

        # Reshape surviving target bones once per component when using FIRST_OF_CHAIN.
        # ACTIVE keeps old behavior: one global target, no component splitting needed.
        if self.target_bone == 'FIRST_OF_CHAIN':
            for component in analysis["components"]:
                target_bone = self.get_component_target_bone(context, component)
                if target_bone is None:
                    continue

                self.reshape_target_bone(target_bone, component, merge_mode)

        else:
            active_bone = context.active_bone
            if active_bone is not None:
                # For ACTIVE, use the full selection as the analysis basis.
                self.reshape_target_bone(active_bone, self.analyze_component(selected_bones), merge_mode)

        self.merge_vertex_groups_for_target_map(context, target_map)
        self.delete_bones_for_target_map(context, target_map)

        print("Resetting X mirror setting for armature to before script state")
        context.active_object.data.use_mirror_x = originalXmirrorSetting

        print("Merging Done!!!")
        return {'FINISHED'}


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
