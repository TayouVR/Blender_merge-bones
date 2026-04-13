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
    "version": (1, 3, 0),
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

    target_bone: EnumProperty(
        name="Target Bone",
        description="Choose which bone survives the merge",
        items=[
            ('AUTO', "Auto", "Use first/root for a single chain or simple branching chain; otherwise use active"),
            ('ACTIVE', "Active", "Always merge into the active bone"),
            ('FIRST', "First", "Always merge into the first/root bone in the selected chain"),
        ],
        default='AUTO',
    )

    merge_mode: EnumProperty(
        name="Merge Mode",
        description="Choose how the surviving bone is reshaped",
        items=[
            ('AUTO', "Auto", "Move the tail to the end bone for single chain, or average end positions for branching; otherwise use keep"),
            ('KEEP', "Keep", "Do not change the bone shape"),
            ('ADJUST_END', "Adjust End", "Move the tail to the end bone, or average end positions for branching"),
            ('FULL_AVERAGE', "Full Average", "Move both head and tail based on the selection"),
        ],
        default='AUTO',
    )

    merge_mode_internal: str = 'AUTO'

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

                vertex_weight_S = vertex_weight_T = vertex_weight_SUM = 0
                if object.vertex_groups[vertex_group_source].index in available_groups:
                    vertex_weight_S = object.vertex_groups[vertex_group_source].weight(id)
                if object.vertex_groups[vertex_group_target].index in available_groups:
                    vertex_weight_T = object.vertex_groups[vertex_group_target].weight(id)

                vertex_weight_SUM = vertex_weight_S + vertex_weight_T
                # only add to vertex group if weight is > 0
                if vertex_weight_SUM > 0:
                    object.vertex_groups[vertex_group_target].add([id], vertex_weight_SUM, 'REPLACE')

            # TODO test if this removes the vertex group
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
            component = set()

            while stack:
                bone = stack.pop()
                if bone in component:
                    continue

                component.add(bone)
                unvisited.discard(bone)

                if bone.parent in selected_set:
                    stack.append(bone.parent)

                for child in bone.children:
                    if child in selected_set:
                        stack.append(child)

            components.append(list(component))

        analyzed_components = [self.analyze_component(component) for component in components]
        active_bone = bpy.context.active_bone

        return {
            "components": analyzed_components,
            "component_count": len(analyzed_components),
            "active_component_index": next(
                (i for i, c in enumerate(analyzed_components) if active_bone in c["bones"]),
                None
            ),
        }

    def get_component_target_bone(self, context, analysis, component):
        active_bone = context.active_bone

        if active_bone is None or not component["bones"]:
            return None

        if self.target_bone == 'ACTIVE':
            return active_bone if active_bone in component["bones"] else component["roots"][0] if component["roots"] else active_bone

        if self.target_bone == 'FIRST':
            return component["roots"][0] if component["roots"] else active_bone

        # AUTO
        # Prefer the component root when that component is cleanly rooted.
        # If not, fall back to active only inside the active component,
        # otherwise fall back to the component root.
        if component["root_count"] == 1:
            return component["roots"][0]

        if active_bone in component["bones"]:
            return active_bone

        return component["roots"][0] if component["roots"] else active_bone

    def average_vector(self, vectors):
        if not vectors:
            return None

        total = vectors[0].copy()
        for vec in vectors[1:]:
            total += vec
        return total / len(vectors)

    def get_selection_head_tail(self, target_bone, analysis):
        roots = analysis["roots"]
        leaves = analysis["leaves"]

        head = target_bone.head.copy()
        tail = target_bone.tail.copy()

        if self.merge_mode_internal == 'KEEP':
            return head, tail

        if self.merge_mode_internal == 'ADJUST_END':
            if leaves:
                tail = self.average_vector([bone.tail.copy() for bone in leaves]) or tail
            return head, tail

        # FULL_AVERAGE
        if roots:
            head = self.average_vector([bone.head.copy() for bone in roots]) or head
        if leaves:
            tail = self.average_vector([bone.tail.copy() for bone in leaves]) or tail

        return head, tail

    def reshape_target_bone(self, target_bone, analysis):
        if target_bone is None:
            return

        head, tail = self.get_selection_head_tail(target_bone, analysis)

        if self.merge_mode_internal == 'FULL_AVERAGE':
            target_bone.head = head
            target_bone.tail = tail
        elif self.merge_mode_internal == 'ADJUST_END':
            target_bone.tail = tail

    def find_objects_with_armature_and_merge(self, context, target_map):
        for object in bpy.data.objects:
            for modifier in object.modifiers:
                if isinstance(modifier, bpy.types.ArmatureModifier):
                    if modifier.object is context.active_object:
                        print("handling object: " + object.name)
                        for source_bone, target_bone in target_map.items():
                            if target_bone is None or source_bone == target_bone:
                                continue
                            print("merging " + source_bone.name + " into " + target_bone.name)
                            self.merge_vertex_groups(object, target_bone.name, source_bone.name)

    def build_target_map(self, context, analysis):
        target_map = {}

        for component in analysis["components"]:
            target_bone = self.get_component_target_bone(context, analysis, component)
            if target_bone is None:
                continue

            for source_bone in component["bones"]:
                target_map[source_bone] = target_bone

        return target_map

    def reshape_components(self, target_map, analysis):
        # Reshape each surviving target bone once, using its own component analysis
        reshaped_targets = set()

        for component in analysis["components"]:
            target_bone = self.get_component_target_bone(bpy.context, analysis, component)
            if target_bone is None or target_bone in reshaped_targets:
                continue

            self.reshape_target_bone(target_bone, component)
            reshaped_targets.add(target_bone)

    def delete_bones(self, context, target_map):
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

        self.merge_mode_internal = self.merge_mode
        if self.merge_mode_internal == 'AUTO':
            # AUTO merge mode: conservative per-component default
            self.merge_mode_internal = 'KEEP'
            if analysis["components"][0]["root_count"] == 1:
                self.merge_mode_internal = 'ADJUST_END'

        target_map = self.build_target_map(context, analysis)

        self.find_objects_with_armature_and_merge(context, target_map)
        self.reshape_components(target_map, analysis)
        self.delete_bones(context, target_map)

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
