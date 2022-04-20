import os
import json
import random
from enum import Enum

import PIL
from PIL import Image, ImageTk

from tkinter import *


width, height      = 1000, 1000
img_range          = [-1, -1]
files_list         = None
boxes              = []
box_corners        = []
boxes_coords       = []
confirmed_assocs   = []
assoc_list         = []
assoc_lines        = []
active_obj         = None
click_start        = [-1, -1]
circle_r           = 5
edit_type          = None
editbox_idx        = None


class States(Enum):
    BOX   = 1
    ASSOC = 2
    CLASS = 3
    EDIT  = 4
    TL_RESIZE_EDIT = 5
    TR_RESIZE_EDIT = 6
    BL_RESIZE_EDIT = 7
    BR_RESIZE_EDIT = 8
    SHIFT_EDIT  = 9

state       = States.BOX

# GLOBAL OBJECTS

root = Tk()
root.title('Comic Dataset Annotator')
root.attributes('-fullscreen', True)

scr_w, scr_h = root.winfo_screenwidth(), root.winfo_screenheight()

canvas = Canvas(
    root, width=scr_w, height=scr_h, bd=0, highlightthickness=0, bg="white")
canvas.pack()

def _create_circle(self, x, y, r, **kwargs):
    return self.create_oval(x-r, y-r, x+r, y+r, **kwargs)
canvas.create_circle = _create_circle

exit_btn = Button(
        root, text="X", font=("Courier", 14), width=2, 
        fg="white", bg= "red", command=root.destroy)

exit_btn.place(relx=0.99, rely=0.01, anchor="ne")

# Global Scene Objects
username     = StringVar()
ratio        = None

welcome = {
    "btn": None,
    "container": None,
}

association = {
    "next_btn": None,
    "pass_btn": None,
    "curr_img": None,
    "panel_btn": None,
    "bubble_btn": None,
    "narrative_btn": None,
    "face_btn": None,
    "body_btn": None,
    "tail_btn": None,
    "container": None,
    "separator": None
}

colors = {
    "face": "green",
    "body": "light blue",
    "panel": "yellow",
    "bubble": "magenta",
    "tail": "pink",
    "narrative": "purple",
}

finish = {
    "container": None
}

scenes = [welcome, association, finish]


def disable_screen_objs():
    for scene in scenes:
        for k in scene.keys():
            if scene[k] is not None and hasattr(scene[k], 'destroy'):

                scene[k].destroy()
                scene[k] = None
    delete_boxes()
    delete_circles()
    delete_lines()


def read_users_list():
    with open("meta_data/users_range.json") as f:
        users = json.load(f)
    return users


def read_file_list():
    with open("meta_data/files_list.txt") as f:
        files = f.readlines()
    
    for i in range(len(files)):
        if files[i][-1] == "\n":
            files[i] = files[i][:-1]
    
    return files


def set_related_files():
    global files_list

    files = read_file_list()
    users = read_users_list()
    if username.get().lower().strip() in users:
        img_range = users[username.get()]
    else:
        img_range = [0, len(files)]
    files_list = files[img_range[0]: img_range[1]]


def show_image():
    global ratio, files_list, association, canvas
    
    filepath = f'annot_images/{files_list[0]}'
    img = PIL.Image.open(filepath)
    w, h = img.size

    if w / h > scr_w / scr_h:
        img_w, img_h = scr_w, int(h * (scr_w/w))
        ratio = scr_w / w
    else:
        img_w, img_h = int(w * (scr_h/h)), scr_h
        ratio = scr_h / h
    
    img = img.resize((img_w, img_h))
    association["curr_img"] = ImageTk.PhotoImage(img)
    
    canvas.create_image(
        scr_w//2, scr_h//2, image=association["curr_img"], anchor=CENTER)


def pass_current_image():
    global files_list
    files_list = files_list[1:] + [files_list[0]]
    show_image()


def set_next_image():
    global files_list, state
    
    last_file = files_list[0]
    files_list = files_list[1:]
    
    if len(files_list) < 1:
        finish_screen()
    else:
        delete_boxes()
        delete_circles()
        delete_lines()
        show_image()
        state = States.BOX
        confirmed_assocs   = []
        assoc_list         = []
        click_start        = [-1, -1]

    
    # TODO: deal with annotations given by users


def set_state(event):
    global state, assoc_list

    if event.char in ['b', 'B']:
        state = States.BOX
        canvas.bind("<ButtonPress-1>", create_box)
        canvas.bind("<B1-Motion>", edit_box)
        canvas.bind("<ButtonRelease-1>", finish_box)
    elif event.char in ['a', 'A']:
        state = States.ASSOC
        canvas.bind("<ButtonPress-1>", assoc_add)
        canvas.unbind("<B1-Motion>")
        canvas.unbind("<ButtonRelease-1>")

        if len(assoc_list) > 1:
            assoc_finalize()
        else:
            assoc_list = []

    elif event.char in ['e', 'E']:
        state = States.EDIT
        canvas.bind("<ButtonPress-1>", edit_start)
        canvas.bind("<B1-Motion>", edit_continue)
        canvas.bind("<ButtonRelease-1>", edit_end)
        draw_circles()
    elif state == States.ASSOC and event.char in ['n', 'N']:
        if len(assoc_list) > 1:
            assoc_finalize()
        else:
            assoc_list = []
    else:
        print("[WARNING] Wrong key is pressed for the state!")
    
    if state != States.EDIT:
        delete_circles()

#############################################################################
### ASSOCIATION MODE METHODS
#############################################################################

def assoc_add(event):
    global boxes_coords, assoc_list, canvas
    x, y = event.x, event.y
    
    box_info = [-1, 10000000000] # idx, area
    for i, (x1, y1, x2, y2) in enumerate(boxes_coords):
        if x1 <= x and x <= x2 and y1 <= y and y <= y2:
            area = (x2 - x1) * (y2 - y1)
            if area < box_info[1]:
                box_info = [i, area]
    
    idx = box_info[0]
    if idx != -1:
        assoc_list.append(idx)
        # canvas.itemconfig(boxes[idx], fill='#a83432')

        if len(assoc_list) > 1:
            x1, y1, x2, y2 = boxes_coords[assoc_list[-2]]
            ax1, ay1 = (x1 + x2) // 2, (y1 + y2) // 2
            x1, y1, x2, y2 = boxes_coords[assoc_list[-1]]
            ax2, ay2 = (x1 + x2) // 2, (y1 + y2) // 2
            assoc_lines.append(
                canvas.create_line(ax1, ay1, ax2, ay2, fill="red", width=3))


def assoc_finalize():
    global assoc_list, confirmed_assocs
    confirmed_assocs.append(assoc_list)
    # for idx in assoc_list:
    #     canvas.itemconfig(boxes[idx], fill='')
    assoc_list = []


def delete_lines():
    global assoc_lines, canvas
    for line in assoc_lines:
        canvas.delete(line)
    assoc_lines = []


#############################################################################
### BOX EDITING MODE METHODS
#############################################################################

def edit_corners():
    global boxes_coords, boxes, box_corners, editbox_idx
    x1, y1, x2, y2 = boxes_coords[editbox_idx]
    canvas.coords(
        box_corners[editbox_idx][0], x1-circle_r, y1-circle_r, x1+circle_r, y1+circle_r)
    canvas.coords(
        box_corners[editbox_idx][1], x2-circle_r, y1-circle_r, x2+circle_r, y1+circle_r)
    canvas.coords(
        box_corners[editbox_idx][2], x1-circle_r, y2-circle_r, x1+circle_r, y2+circle_r)
    canvas.coords(
        box_corners[editbox_idx][3], x2-circle_r, y2-circle_r, x2+circle_r, y2+circle_r)


def draw_circles():
    global canvas, box_corners, boxes_coords
    for i, (x1, y1, x2, y2) in enumerate(boxes_coords):
        color = canvas.itemcget(boxes[i], "outline")
        circles = [
            canvas.create_oval(
                x1-circle_r, y1-circle_r, x1+circle_r, y1+circle_r, 
                fill=color, outline=color, width=1),
            canvas.create_oval(
                x2-circle_r, y1-circle_r, x2+circle_r, y1+circle_r, 
                fill=color, outline=color, width=1),
            canvas.create_oval(
                x1-circle_r, y2-circle_r, x1+circle_r, y2+circle_r, 
                fill=color, outline=color, width=1),
            canvas.create_oval(
                x2-circle_r, y2-circle_r, x2+circle_r, y2+circle_r, 
                fill=color, outline=color, width=1)
        ]
        box_corners.append(circles)

def delete_circles():
    global box_corners, canvas
    for corners in box_corners:
        for circle in corners:
            canvas.delete(circle)
    box_corners = []

def edit_start(event):
    global edit_type, editbox_idx, circle_r, click_start
    x, y = event.x, event.y

    box_info = [-1, 10000000000] # idx, area
    for i, (x1, y1, x2, y2) in enumerate(boxes_coords):
        if (x1 - circle_r <= x and x <= x2 + circle_r 
            and y1 - circle_r <= y and y <= y2 + circle_r):
            
            area = (x2 - x1) * (y2 - y1)
            if area < box_info[1]:
                box_info = [i, area]

    if box_info[0] != -1:
        editbox_idx = box_info[0]
        x1, y1, x2, y2 = boxes_coords[editbox_idx]
        if abs(x-x1) <= circle_r and abs(y-y1) <= circle_r:
            edit_type = States.TL_RESIZE_EDIT
        elif abs(x-x2) <= circle_r and abs(y-y1) <= circle_r:
            edit_type = States.TR_RESIZE_EDIT
        elif abs(x-x1) <= circle_r and abs(y-y2) <= circle_r:
            edit_type = States.BL_RESIZE_EDIT
        elif abs(x-x2) <= circle_r and abs(y-y2) <= circle_r:
            edit_type = States.BR_RESIZE_EDIT
        else:
            edit_type = States.SHIFT_EDIT
    else:
        print(x, y)
        print(boxes_coords)
    
    click_start = [x, y]


def edit_continue(event):
    global boxes, boxes_coords, editbox_idx, click_start, canvas
    x, y = event.x, event.y

    if editbox_idx is None:
        print("[ERROR] Box to edit cannot be found!")
    else:
    # print(boxes_coords, editbox_idx)
        x1, y1, x2, y2 = boxes_coords[editbox_idx]

        if edit_type == States.TL_RESIZE_EDIT:
            boxes_coords[editbox_idx] = [x, y, x2, y2]
        elif edit_type == States.TR_RESIZE_EDIT:
            boxes_coords[editbox_idx] = [x1, y, x, y2]
        elif edit_type == States.BL_RESIZE_EDIT:
            boxes_coords[editbox_idx] = [x, y1, x2, y]
        elif edit_type == States.BR_RESIZE_EDIT:
            boxes_coords[editbox_idx] = [x1, y1, x, y]
        
        elif edit_type == States.SHIFT_EDIT:
            if click_start[0] >= 0:
                x_s = click_start[0] - x
                y_s = click_start[1] - y
                boxes_coords[editbox_idx] = [x1-x_s, y1-y_s, x2-x_s, y2-y_s]
                click_start = [x, y]

        canvas.coords(boxes[editbox_idx], *boxes_coords[editbox_idx])
        edit_corners()

def edit_end(event):
    global boxes, boxes_coords, canvas, editbox_idx

    if editbox_idx is not None:
        x1, y1, x2, y2 = boxes_coords[editbox_idx]
        boxes_coords[editbox_idx] = [
            min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]

        canvas.coords(boxes[editbox_idx], *boxes_coords[editbox_idx])
        edit_corners()
    
    editbox_idx = None
    click_start = [-1, -1]

#############################################################################
### BOX DRAWING MODE METHODS
#############################################################################

def create_box(event):
    global boxes, canvas, click_start, active_obj
    click_start = [event.x, event.y]
    # r = lambda: random.randint(0,255)
    # color = '#{:02x}{:02x}{:02x}'.format(r(), r(), r())
    if active_obj is not None:
        boxes.append(
            canvas.create_rectangle(event.x, event.y, event.x+1, event.y+1, 
            outline=colors[active_obj], fill="", width=5)
        )

def delete_boxes():
    global boxes, boxes_coords, canvas
    for box in boxes:
        canvas.delete(box)
    boxes = []
    boxes_coords = []


def edit_box(event):
    global boxes, canvas, click_start, active_obj
    if active_obj is not None:
        canvas.coords(boxes[-1], *click_start, event.x, event.y)  


def change_box_color(typ):
    global active_obj
    if active_obj is not None:
        association[active_obj + "_btn"].config(font=("Courier", 14))
    active_obj = typ
    association[active_obj + "_btn"].config(font=("Courier", 14, "bold", "underline"))



def finish_box(event):
    global boxes, canvas, click_start, boxes_coords, active_obj
    
    if active_obj is not None:
        canvas.coords(boxes[-1], *click_start, event.x, event.y)
        final_coords = [*click_start, event.x, event.y]

        x, y, x1, y1 = event.x, event.y, *click_start
        final_coords = [min(x, x1), min(y, y1), max(x, x1), max(y, y1)]
        boxes_coords.append(final_coords)
        click_start = [-1, -1]
        # TODO: save box and create a class selection screen

#############################################################################

def annot_screen():
    global canvas, association

    disable_screen_objs()
    set_related_files()

    root.bind("<Key>", set_state)
    canvas.bind("<ButtonPress-1>", create_box)
    canvas.bind("<B1-Motion>", edit_box)
    canvas.bind("<ButtonRelease-1>", finish_box)

    association["container"] = Label(
        root, font=("Courier", 14), text="""Shortcuts / Modes:
------------------------------------------
* B --> bounding box draw mode
* E --> box edit mode
* A --> face-body-bubble association mode
* N --> before doing next association""")
    association["container"].config(bg="#b8e5eb", padx=10, pady=10, justify=LEFT)
    association["container"].place(relx=0.01, rely=0.01, anchor="nw")

    association["next_btn"] = Button(
        root, text="NEXT IMAGE", font=("Courier", 14), width=15, 
        fg="#121111", bg= "gray", command=set_next_image)
    association["next_btn"].place(relx=0.03, rely=0.17, anchor="nw")

    association["pass_btn"] = Button(
        root, text="PASS", font=("Courier", 14), width=15, 
        fg="#121111", bg= "gray", command=pass_current_image)
    association["pass_btn"].place(relx=0.15, rely=0.17, anchor="nw")

    association["separator"] = Label(
        root, font=("Courier", 14), text="------------------------------------------")
    association["separator"].config(bg="white", padx=10, pady=10, justify=LEFT)
    association["separator"].place(relx=0.01, rely=0.22, anchor="nw")

    association["face_btn"] = Button(
        root, text="FACE", font=("Courier", 14), width=15, 
        fg="#121111", bg= colors["face"], command=lambda: change_box_color("face"))
    association["face_btn"].place(relx=0.03, rely=0.27, anchor="nw")
    
    association["body_btn"] = Button(
        root, text="BODY", font=("Courier", 14), width=15, 
        fg="#121111", bg= colors["body"], command=lambda: change_box_color("body"))
    association["body_btn"].place(relx=0.15, rely=0.27, anchor="nw")

    association["panel_btn"] = Button(
        root, text="PANEL", font=("Courier", 14), width=15, 
        fg="#121111", bg= colors["panel"], command=lambda: change_box_color("panel"))
    association["panel_btn"].place(relx=0.03, rely=0.32, anchor="nw")

    association["narrative_btn"] = Button(
        root, text="NARRATIVE", font=("Courier", 14), width=15, 
        fg="#121111", bg= colors["narrative"], command=lambda: change_box_color("narrative"))
    association["narrative_btn"].place(relx=0.15, rely=0.32, anchor="nw")

    association["bubble_btn"] = Button(
        root, text="SPEECH BALLOON", font=("Courier", 14), width=15, 
        fg="#121111", bg= colors["bubble"], command=lambda: change_box_color("bubble"))
    association["bubble_btn"].place(relx=0.03, rely=0.37, anchor="nw")

    association["tail_btn"] = Button(
        root, text="BALLOON TAIL", font=("Courier", 14), width=15, 
        fg="#121111", bg= colors["tail"], command=lambda: change_box_color("tail"))
    association["tail_btn"].place(relx=0.15, rely=0.37, anchor="nw")


    show_image() 


def welcome_screen():

    welcome["container"] = Label(root, text="")
    welcome["container"].config(bg="#b8e5eb", padx=200, pady=80)
    welcome["container"].place(relx=0.5, rely=0.5, anchor="center")

    instruction = Label(welcome["container"], text="Please enter your name:")
    instruction.config(bg="#b8e5eb", font=("Courier", 16))
    instruction.place(relx=0.5, rely=0.15, anchor="center")

    user = Entry(
        welcome["container"], textvariable=username, font=("Courier", 16), 
        bd=0, width=13, bg="white", justify="center")
    user.insert(0, 'Your Name')
    # user.insert(0, 'test')
    user.place(relx=0.5, rely=0.4, anchor="center")
   
    welcome["btn"] = Button(
        welcome["container"], text="START", font=("Courier", 14), width=15, 
        fg="#121111", bg= "#E4E4E0", command=annot_screen)

    welcome["btn"].place(relx=0.5, rely=0.7, anchor="center")

def finish_screen():
    disable_screen_objs()
    canvas.delete("all")

    finish["container"] = Label(root, text="")
    finish["container"].config(bg="#b8e5eb", padx=500, pady=100)
    finish["container"].place(relx=0.5, rely=0.5, anchor="center")
    instruction = Label(
        finish["container"], 
        text="""Your assigned files are finished.
Please ZIP the "results" folder and send to Baris.

Thanks for participating :)""")
    
    instruction.config(bg="#b8e5eb", font=("Courier", 16))
    instruction.place(relx=0.5, rely=0.5, anchor="center")

welcome_screen()
root.mainloop()