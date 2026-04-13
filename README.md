# Bone and Vertex Group Merge
Blender Plugin to merge any number of selected bones, with respect to any meshes and their vertex groups.

## Installation

### From extensions.blender.org (blender 4.2.0+)
1. in blender, open Preferences and go to "Get Extensions"
2. search "Bone and Vertex Group Merge"
3. Install

link: https://extensions.blender.org/add-ons/org-tayou-bone-vertex-group-merge/

### From GitHub
1. download the .py file
2. in blender, Preferences > Add-ons > install
3. enable Addon

## Usage
- select the armature you wish to edit
- select the bones you want to merge
- rick click, at the bottom "merge Bones"

Use the operator properties in the bottom left to adjust behaviour. You can merge multiple bone chains at once, each chain will be merged individually by default. You can also merge all selected bones into the active bone, ignoring their hierarchical position.

## Example
### Before
![image](https://user-images.githubusercontent.com/31988415/227536194-7b96ba41-e86c-4036-946f-655895d59ce3.png)
![image](https://user-images.githubusercontent.com/31988415/227536871-5e3e965a-0673-448e-8beb-141de791e9e0.png)
### After
![image](https://user-images.githubusercontent.com/31988415/227536257-9975ee31-2df3-4174-a9f6-2f9496909c9d.png)
![image](https://user-images.githubusercontent.com/31988415/227536754-7ebb4e50-3296-452f-9427-ddc4cc60312c.png)

# Building Extension (blender 4.2.0+)
```shell
blender --command extension build
```
