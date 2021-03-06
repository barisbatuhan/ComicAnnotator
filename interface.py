import os
import json
import random
from enum import Enum

import PIL
from PIL import Image, ImageTk

from tkinter import *
from tkinter.scrolledtext import ScrolledText

class States(Enum):
    BOX   = 1
    ASSOC = 2
    CLASS = 3
    EDIT  = 4
    IDENT = 10 
    OCR   = 11
    OCR_ACTIVE = 13
    GAZE  = 12 # TO DO
    TL_RESIZE_EDIT = 5
    TR_RESIZE_EDIT = 6
    BL_RESIZE_EDIT = 7
    BR_RESIZE_EDIT = 8
    SHIFT_EDIT     = 9

def get_state_lbl():
    global state

    if state == States.BOX:
        return "Mode: DRAW BOXES"
    elif state == States.ASSOC:
        return "Mode: ASSOCIATE"
    elif state == States.EDIT:
        return "Mode: EDIT BOXES"
    elif state == States.IDENT:
        return "Mode: MATCH BODIES"
    elif state == States.OCR or state == States.OCR_ACTIVE:
        return "Mode: TEXT TRANSCRIPT"


class Acts(Enum):
    BOX    = 1
    LINE   = 2
    IDENT  = 5
    INIT   = 3
    FINISH = 4

state              = States.BOX
img_range          = [-1, -1]
img_sizes          = [-1, -1, -1, -1] # orig_w, orig_h, resized_w, resized_h
files_list         = None
boxes              = []
boxes_coords       = []
boxes_objects      = []
box_corners        = []
confirmed_assocs   = []
assoc_list         = []
assoc_lines        = []
active_obj         = None
click_start        = [-1, -1]
circle_r           = 5
edit_type          = None
editbox_idx        = None
curr_ident_color   = None
ident_dots         = []
ident_box_indices  = []

ocr_boxes          = []
ocr_box_ids        = []
ocr_last_box       = -1

last_actions       = [Acts.INIT]

inst_end_val       = 0.27
bar_end_line       = 550

# GLOBAL OBJECTS

root = Tk()
root.title('Comic Dataset Annotator')
root.attributes('-fullscreen', True)

scr_w, scr_h = root.winfo_screenwidth(), root.winfo_screenheight()

canvas = Canvas(
    root, width=scr_w, height=scr_h, bd=0, highlightthickness=0, bg="white")
canvas.pack()

exit_btn = Button(
        root, text="X", font=("Courier", 14), width=2, 
        fg="white", bg= "red", command=root.destroy)

exit_btn.place(relx=0.99, rely=0.01, anchor="ne")

# Global Scene Objects
username     = StringVar()
bubble_txt   = StringVar()
ratio        = None

welcome = {
    "btn": None,
    "container": None,
}

annotation = {
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
    "separator": None,
    "vert_separator": None,
    "undo_btn": None,
    "clear_btn": None,
    "state_lbl": None,
    "vert_separator": None,
}

ocr_input = {
    "container": None,
    "entry": None,
    "confirm_btn": None,
    "txt_content": None
}

finish = {
    "container": None
}

scenes = [welcome, annotation, ocr_input, finish]

colors = {
    "face": "green",
    "body": "blue",
    "panel": "yellow",
    "bubble": "magenta",
    "tail": "pink",
    "narrative": "purple",
}

# def create_rectangle(x1, y1, x2, y2, **kwargs):
#     if 'alpha' in kwargs:
#         alpha = int(kwargs.pop('alpha') * 255)
#         fill = kwargs.pop('fill')
#         fill = root.winfo_rgb(fill) + (alpha,)
#         image = Image.new('RGBA', (x2-x1, y2-y1), fill)
#         canvas.create_image(x1, y1, image=image, anchor='nw')
#     canvas.create_rectangle(x1, y1, x2, y2, **kwargs)

def disable_screen_objs():
    for scene in scenes:
        for k in scene.keys():
            if scene[k] is not None and hasattr(scene[k], 'destroy'):

                scene[k].destroy()
                scene[k] = None
    delete_boxes()
    delete_circles()
    delete_lines()
    delete_identities()


def close_app(*args):
    root.destroy()


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
    global ratio, files_list, annotation, canvas, img_sizes, bar_end_line
    
    filepath = f'annot_images/{files_list[0]}'
    img = PIL.Image.open(filepath)
    w, h = img.size

    img_sizes[0] = w
    img_sizes[1] = h

    avail_w = scr_w - bar_end_line - 10

    if w / h > avail_w / scr_h:
        img_w, img_h = avail_w, int(h * (avail_w/w))
        ratio = avail_w / w
    else:
        img_w, img_h = int(w * (scr_h/h)), scr_h
        ratio = scr_h / h

    img_sizes[2] = img_w
    img_sizes[3] = img_h
    
    img = img.resize((img_w, img_h))
    annotation["curr_img"] = ImageTk.PhotoImage(img)
    
    canvas.create_image(
        10 + bar_end_line + avail_w//2, scr_h//2, image=annotation["curr_img"], anchor=CENTER)


def pass_current_image():
    global files_list
    files_list = files_list[1:] + [files_list[0]]
    show_image()


def set_next_image(*args):
    global files_list, state, confirmed_assocs, assoc_list, click_start
    global ident_box_indices, ident_dots, img_sizes, scr_w, scr_h
    global ocr_last_box
    
    if state == States.IDENT:
        exit_identity_mode()
    elif state == States.OCR or state == States.OCR_ACTIVE:
        exit_text_mode()

    if len(assoc_list) > 0:
        confirmed_assocs.append(assoc_list)
        assoc_list = []

    last_file = files_list[0]
    files_list = files_list[1:]

    if len(boxes) > 0:
        f = open(os.path.join('results/', last_file[:last_file.rfind(".")] + ".txt"), "w")
        f.write("### BOXES\n")

        color_map = {}
        for k in colors.keys():
            color_map[colors[k]] = k

        for idx, (box, (x1, y1, x2, y2)) in enumerate(zip(boxes, boxes_coords)):
            color = canvas.itemcget(box, "outline")

            avail_w = scr_w - bar_end_line - 10

            res_w, res_h = img_sizes[2], img_sizes[3]
            orig_w, orig_h = img_sizes[0], img_sizes[1]
            pg_hw, pg_hh = 5 + bar_end_line + avail_w / 2, scr_h / 2
            res_hw, res_hh = res_w / 2, res_h / 2

            left_x, top_y = pg_hw - res_hw, pg_hh - res_hh

            x1 = int(max(0, x1 - left_x) * orig_w / res_w)
            x2 = int(min(res_w, x2 - left_x) * orig_w / res_w)
            y1 = int(max(0, y1 - top_y) * orig_h / res_h)
            y2 = int(min(res_h, y2 - top_y) * orig_h / res_h)

            f.write(f"{idx},{x1},{y1},{x2},{y2},{color_map[color]}\n")
        
        f.write("\n### ASSOCIATIONS\n")
        for lines in confirmed_assocs:
            txt = "".join([str(idx) + "," for idx in lines])
            f.write(txt[:-1] + "\n")

        f.write("\n### IDENTIFICATIONS\n")
        colors_dict = {}
        for id_idx, dot in enumerate(ident_dots):
            color = canvas.itemcget(dot, "fill")
            if color not in colors_dict.keys():
                colors_dict[color] = []
            colors_dict[color].append(ident_box_indices[id_idx])

        for k in colors_dict.keys():
            txt = "".join([str(idx) + "," for idx in colors_dict[k]])
            f.write(txt[:-1] + "\n")

        f.write("\n### TEXTS\n")
        for bidx, txt in zip(ocr_box_ids, ocr_boxes):
            f.write(f"{bidx},{txt}")


    if len(files_list) < 1:
        finish_screen()
    else:
        clear_canvas()
        show_image()
        state = States.BOX
        confirmed_assocs   = []
        assoc_list         = []
        click_start        = [-1, -1]


def set_state(event):
    global state, assoc_list, annotation

    if state == States.OCR_ACTIVE:
        return 0

    if state == States.IDENT and event.char not in ["i", "I", "N", "n"]:
        exit_identity_mode()
    elif state == States.OCR and event.char not in ["t", "T"]:
        exit_text_mode()

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
    
    elif event.char in ['n', 'N']:
        if state == States.ASSOC:
            if len(assoc_list) > 1:
                assoc_finalize()
            else:
                assoc_list = []
        elif state.IDENT:
            new_identity()
    
    elif event.char in ["i", "I"]:
        enter_identity_mode()
        state = States.IDENT
        canvas.bind("<ButtonPress-1>", add_identity)
        canvas.unbind("<B1-Motion>")
        canvas.unbind("<ButtonRelease-1>")
    
    elif event.char in ["t", "T"]:
        enter_text_mode()
        state = States.OCR
        canvas.bind("<ButtonPress-1>", on_bubble_click)
        canvas.unbind("<B1-Motion>")
        canvas.unbind("<ButtonRelease-1>")
    
    # else:
    #     print(f"[WARNING] Wrong key is pressed for the state: {event.char}!")
    
    if state != States.EDIT:
        delete_circles()
    
    if annotation["state_lbl"] is not None:
        annotation["state_lbl"]['text'] = get_state_lbl()


#############################################################################
### UNDO AND DELETE MODE METHODS
#############################################################################

def undo_changes(*args):

    global last_actions, boxes, box_corners, boxes_coords, assoc_list
    global assoc_lines, confirmed_assocs, boxes_objects, ident_box_indices, ident_dots
    global ocr_boxes, ocr_box_ids

    if len(last_actions) > 0:
        last_action = last_actions.pop()

        if last_action == Acts.INIT or last_action == Acts.FINISH:
            # add initial/final state again and do nothing
            last_actions.append(last_action)
        
        elif last_action == Acts.BOX and len(boxes) > 0:
            latest_box = len(boxes) - 1

            ocr_id = 0
            while ocr_id < len(ocr_boxes):
                if ocr_box_ids[ocr_id] != latest_box:
                    ocr_id += 1
                else:
                    ocr_box_ids = ocr_box_ids[:ocr_id] + ocr_box_ids[ocr_id+1:]
                    ocr_boxes = ocr_boxes[:ocr_id] + ocr_boxes[ocr_id+1:]

            canvas.delete(boxes[-1])
            boxes = boxes[:-1]
            boxes_coords = boxes_coords[:-1]
            boxes_objects = boxes_objects[:-1]
            if len(box_corners) > 0:
                for circle in box_corners[-1]:
                    canvas.delete(circle)
                box_corners = box_corners[:-1]
        
        elif last_action == Acts.LINE:
            # if there is a current association going on,
            # one last line is deleted
            if len(assoc_list) == 1:
                assoc_list = []
            elif len(assoc_list) > 1:
                assoc_list = assoc_list[:-1]
                canvas.delete(assoc_lines[-1])
                assoc_lines = assoc_lines[:-1]
            # if an entire association is finished, entire is undone
            elif len(confirmed_assocs) > 0:
                last_assoc = confirmed_assocs[-1]
                assoc_list = last_assoc
                confirmed_assocs = confirmed_assocs[:-1]
                last_actions.append(last_action)
                undo_changes()
        
        elif last_action == Acts.IDENT:
            ident_box_indices = ident_box_indices[:-1]
            last_dot = ident_dots.pop()
            canvas.delete(last_dot)

def clear_canvas(*args):
    global last_actions
    if last_actions[-1] not in [Acts.INIT, Acts.FINISH]:
        delete_boxes()
        delete_circles()
        delete_lines()  
        delete_identities()
        delete_texts()


#############################################################################
### OCR TEXT MODE METHODS
#############################################################################

def enter_text_mode():
    global boxes, boxes_objects, canvas
    for idx, box in enumerate(boxes):
        if boxes_objects[idx] not in ["bubble", "narrative"]:
            canvas.itemconfigure(box, outline="")


def exit_text_mode():
    global ocr_last_box
    for idx, box in enumerate(boxes):
        if boxes_objects[idx] not in ["bubble", "narrative"]:
            canvas.itemconfigure(box, outline=colors[boxes_objects[idx]])
    ocr_last_box = -1

def delete_texts():
    global ocr_box_ids, ocr_boxes, ocr_last_box
    ocr_boxes = []
    ocr_box_ids = []
    ocr_last_box = -1

def on_bubble_click(event):
    global ocr_input, bubble_txt, boxes_coords, boxes_objects, canvas, ocr_last_box
    global state

    x, y = event.x, event.y
    
    box_info = [-1, 10000000000] # idx, area
    for i, (x1, y1, x2, y2) in enumerate(boxes_coords):
        if boxes_objects[i] not in ["bubble", "narrative"]:
            continue
        if x1 <= x and x <= x2 and y1 <= y and y <= y2:
            area = (x2 - x1) * (y2 - y1)
            if area < box_info[1]:
                box_info = [i, area]
    
    idx = box_info[0]
    if idx != -1:
        state = States.OCR_ACTIVE
        ocr_input["container"] = Label(canvas, text="")
        ocr_input["container"].config(bg="#b8e5eb", padx=250, pady=100)
        ocr_input["container"].place(relx=0.01, rely=0.99, anchor="sw")

        ocr_input["entry"] = Label(ocr_input["container"], text="Enter the transcript:")
        ocr_input["entry"].config(bg="#b8e5eb", font=("Courier", 16, "bold"))
        ocr_input["entry"].place(relx=0.5, rely=0.15, anchor="center")

        ocr_input["confirm_btn"] = Button(
            ocr_input["container"], text="CONFIRM", font=("Courier", 12), width=15, 
            fg="#121111", bg="#E4E4E0", command=on_confirm_click)

        ocr_input["confirm_btn"].place(relx=0.5, rely=0.88, anchor="center")

        ocr_input["txt_content"] = Text(
            ocr_input["container"],
            width=42, height=6, font=("Courier", 12))
        ocr_input["txt_content"].place(relx=0.5, rely=0.5, anchor="center")
    
        # TO DO: get also id of the box to global
        ocr_last_box = idx
        

def on_confirm_click():
    global ocr_input, ocr_boxes, ocr_box_ids, ocr_last_box, state
    txt = ocr_input["txt_content"].get("1.0",'end')
    
    state = States.OCR

    if len(txt) > 0:
        ocr_boxes.append(txt)
        ocr_box_ids.append(ocr_last_box)
        ocr_last_box = -1
    
    for k in ocr_input.keys():
        if ocr_input[k] is not None and hasattr(ocr_input[k], 'destroy'):
            ocr_input[k].destroy()
        ocr_input[k] = None


#############################################################################
### IDENTIFICATION MODE METHODS
#############################################################################

def enter_identity_mode():
    global boxes, boxes_objects, canvas
    for idx, box in enumerate(boxes):
        if boxes_objects[idx] != "body":
            canvas.itemconfigure(box, outline="")


def exit_identity_mode():
    for idx, box in enumerate(boxes):
        if boxes_objects[idx] != "body":
            canvas.itemconfigure(box, outline=colors[boxes_objects[idx]])


def delete_identities():
    global ident_box_indices, ident_dots
    for dot in ident_dots:
        canvas.delete(dot)
    ident_box_indices = []


def new_identity():
    global curr_ident_color
    r = lambda: random.randint(0,255)
    curr_ident_color = '#{:02x}{:02x}{:02x}'.format(r(), r(), r())

def add_identity(event):
    global boxes, boxes_coords, assoc_list, canvas, last_actions
    global curr_ident_color, boxes_objects, ident_dots, ident_box_indices
    x, y = event.x, event.y
    
    box_info = [-1, 10000000000] # idx, area
    for i, (x1, y1, x2, y2) in enumerate(boxes_coords):
        if boxes_objects[i] != "body":
            continue
        if x1 <= x and x <= x2 and y1 <= y and y <= y2:
            area = (x2 - x1) * (y2 - y1)
            if area < box_info[1]:
                box_info = [i, area]

    idx = box_info[0]
    if idx != -1:
        if curr_ident_color is None:
            r = lambda: random.randint(0,255)
            curr_ident_color = '#{:02x}{:02x}{:02x}'.format(r(), r(), r())
        
        x1, y1, x2, y2 = boxes_coords[idx]
        xc = (x1 + x2) // 2
        yc = (y1 + y2) // 2

        found = False
        for dot in ident_dots:
            xl, yt, xr, yb = canvas.coords(dot)
            if xc == (xl + xr) // 2 and yc == (yt + yb) // 2:
                canvas.itemconfigure(dot, fill=curr_ident_color, outline=curr_ident_color)
                found = True
                break
        
        if not found:
            ident_dots.append(
                canvas.create_oval(
                    xc-2*circle_r, yc-2*circle_r, xc+2*circle_r, yc+2*circle_r, 
                    fill=curr_ident_color, outline=curr_ident_color, width=5))
            
            last_actions.append(Acts.IDENT)
            ident_box_indices.append(idx)


#############################################################################
### ASSOCIATION MODE METHODS
#############################################################################

def assoc_add(event):
    global boxes_coords, assoc_list, canvas, last_actions
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
    
    last_actions.append(Acts.LINE)


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
    global boxes, boxes_coords, canvas, editbox_idx, click_start

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
    global boxes, canvas, click_start, active_obj, boxes_objects
    click_start = [event.x, event.y]

    if active_obj is not None:
        boxes.append(
            canvas.create_rectangle(
                event.x, event.y, event.x+1, event.y+1, 
                outline=colors[active_obj], fill="", width=3)
        )
        boxes_objects.append(active_obj)


def delete_boxes():
    global boxes, boxes_coords, canvas, boxes_objects
    for box in boxes:
        canvas.delete(box)
    boxes = []
    boxes_coords = []
    boxes_objects = []


def edit_box(event):
    global boxes, canvas, click_start, active_obj
    if active_obj is not None:
        canvas.coords(boxes[-1], *click_start, event.x, event.y)  


def change_box_color(typ):
    global active_obj
    if active_obj is not None:
        annotation[active_obj + "_btn"].config(font=("Courier", 14))
    active_obj = typ
    annotation[active_obj + "_btn"].config(font=("Courier", 14, "bold", "underline"))


def finish_box(event):
    global boxes, canvas, click_start, boxes_coords, active_obj, last_actions
    
    if active_obj is not None:
        canvas.coords(boxes[-1], *click_start, event.x, event.y)
        final_coords = [*click_start, event.x, event.y]

        x, y, x1, y1 = event.x, event.y, *click_start
        final_coords = [min(x, x1), min(y, y1), max(x, x1), max(y, y1)]
        boxes_coords.append(final_coords)
        last_actions.append(Acts.BOX)
        click_start = [-1, -1]
        # TODO: save box and create a class selection screen

#############################################################################

def annot_screen():
    global canvas, annotation, inst_end_val

    disable_screen_objs()
    set_related_files()

    root.bind("<Key>", set_state)
    root.bind("<Delete>", clear_canvas)
    root.bind("<Control-z>", undo_changes)
    root.bind("<Right>", set_next_image)
    canvas.bind("<ButtonPress-1>", create_box)
    canvas.bind("<B1-Motion>", edit_box)
    canvas.bind("<ButtonRelease-1>", finish_box)

    annotation["container"] = Label(
        root, font=("Courier", 14), text="""Shortcuts / Modes:
------------------------------------------
* B --> bounding box draw mode
* E --> box edit mode
* A --> face-body-bubble association mode
* I --> identification through body matching
* N --> go next association / identification
* T --> OCR mode to transcript bubble text""")
    annotation["container"].config(bg="#b8e5eb", padx=10, pady=10, justify=LEFT)
    annotation["container"].place(relx=0.01, rely=0.06, anchor="nw")

    annotation["state_lbl"] = Label(root, font=("Courier", 14, "bold"), width=44, text=get_state_lbl())
    annotation["state_lbl"].config(bg="#b8e5eb", padx=10, pady=6, justify=LEFT)
    annotation["state_lbl"].place(relx=0.01, rely=0.01, anchor="nw")

    annotation["vert_separator"] = canvas.create_line(bar_end_line, 0, bar_end_line, scr_h, width=5)

    annotation["next_btn"] = Button(
        root, text="NEXT IMG [->]", font=("Courier", 14), width=15, 
        fg="#121111", bg= "gray", command=set_next_image)
    annotation["next_btn"].place(relx=0.03, rely=inst_end_val, anchor="nw")

    annotation["pass_btn"] = Button(
        root, text="PASS", font=("Courier", 14), width=15, 
        fg="#121111", bg= "gray", command=pass_current_image)
    annotation["pass_btn"].place(relx=0.15, rely=inst_end_val, anchor="nw")

    annotation["undo_btn"] = Button(
        root, text="UNDO [Ctrl+Z]", font=("Courier", 14), width=15, 
        fg="#121111", bg= "light gray", command=undo_changes)
    annotation["undo_btn"].place(relx=0.03, rely=inst_end_val + 0.05, anchor="nw")

    annotation["clear_btn"] = Button(
        root, text="CLEAR [DEL]", font=("Courier", 14), width=15, 
        fg="#121111", bg= "light gray", command=clear_canvas)
    annotation["clear_btn"].place(relx=0.15, rely=inst_end_val + 0.05, anchor="nw")

    annotation["separator"] = Label(
        root, font=("Courier", 14), text="------------------------------------------")
    annotation["separator"].config(bg="white", padx=10, pady=10, justify=LEFT)
    annotation["separator"].place(relx=0.01, rely=inst_end_val + 0.1, anchor="nw")

    annotation["face_btn"] = Button(
        root, text="FACE", font=("Courier", 14), width=15, 
        fg="#121111", bg= colors["face"], command=lambda: change_box_color("face"))
    annotation["face_btn"].place(relx=0.03, rely=inst_end_val + 0.15, anchor="nw")
    
    annotation["body_btn"] = Button(
        root, text="BODY", font=("Courier", 14), width=15, 
        fg="#121111", bg= colors["body"], command=lambda: change_box_color("body"))
    annotation["body_btn"].place(relx=0.15, rely=inst_end_val + 0.15, anchor="nw")

    annotation["panel_btn"] = Button(
        root, text="PANEL", font=("Courier", 14), width=15, 
        fg="#121111", bg= colors["panel"], command=lambda: change_box_color("panel"))
    annotation["panel_btn"].place(relx=0.03, rely=inst_end_val + 0.2, anchor="nw")

    annotation["narrative_btn"] = Button(
        root, text="NARRATIVE", font=("Courier", 14), width=15, 
        fg="#121111", bg= colors["narrative"], command=lambda: change_box_color("narrative"))
    annotation["narrative_btn"].place(relx=0.15, rely=inst_end_val + 0.2, anchor="nw")

    annotation["bubble_btn"] = Button(
        root, text="SPEECH BALLOON", font=("Courier", 14), width=15, 
        fg="#121111", bg= colors["bubble"], command=lambda: change_box_color("bubble"))
    annotation["bubble_btn"].place(relx=0.03, rely=inst_end_val + 0.25, anchor="nw")

    annotation["tail_btn"] = Button(
        root, text="BALLOON TAIL", font=("Courier", 14), width=15, 
        fg="#121111", bg= colors["tail"], command=lambda: change_box_color("tail"))
    annotation["tail_btn"].place(relx=0.15, rely=inst_end_val + 0.25, anchor="nw")

    show_image() 


def welcome_screen():

    root.bind("<Escape>", close_app)

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
    
    global finish, last_actions, canvas

    root.unbind("<Delete>")
    root.unbind("<Control-z>")
    root.unbind("<Right>")

    disable_screen_objs()

    last_actions.append(Acts.FINISH)
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