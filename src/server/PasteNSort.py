import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import subprocess
import os
import sys
import time

#Define a width multiplier for how wide the window will be in reference to the screen
WINDOW_WIDTH_MULTIPLIER = 0.28125

#Define number of thumbnails across the window
THUMBNAIL_NUMBER = 3

# These below are used as global variables and will be changed when running
# Save the window_id for the Dolphin browser we open so we can close it again when done
window_id = None

# Define a global variable for thumbnail size - this will be changed below
THUMBNAIL_SIZE = (260, 260)


class ImageGridApp:
    def __init__(self, master):
        """
        Initializes the ImageGridApp.

        Args:
            master: The root Tkinter window.
        """
        self.master = master
        master.title("Copy images --> Click paste button --> Drag to reorder")
        # get the screen width
        screen_width = master.winfo_screenwidth()
        screen_height = master.winfo_screenheight()
        #print (f"width {screen_width} : height {screen_height}")
        geometry = str (int(WINDOW_WIDTH_MULTIPLIER * screen_width)) + "x" + str(screen_height) + "+0+0"
        #print (geometry)
        master.geometry(geometry) # Initial window size
        
        #rededine thumnail size based upon screen size
        thumb_width = ((WINDOW_WIDTH_MULTIPLIER * screen_width) / THUMBNAIL_NUMBER) - (10 * THUMBNAIL_NUMBER) - 2
        #print (thumb_width)
        global THUMBNAIL_SIZE
        THUMBNAIL_SIZE = (int(thumb_width), int(thumb_width))
        
        master.protocol("WM_DELETE_WINDOW", self.on_closing) # handle the user clicking the X to close and cancel
        
        # Configure grid weights for responsive layout
        master.grid_rowconfigure(0, weight=1)
        master.grid_columnconfigure(0, weight=1)

        # Stores {'filename', 'photo_image', 'label'} for each thumbnail.
        # 'label' will be updated dynamically in redraw_grid.
        self.images_data = []
        self.dragged_item = None # Stores the item being dragged
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.drag_original_row = -1
        self.drag_original_col = -1
        self._last_frame_width = 0 # To track frame width for responsive redraws

        # --- Thumbnail Grid Frame ---
        self.grid_frame = tk.Frame(master, bg="#f0f0f0", bd=2, relief="sunken")
        self.grid_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        # Configure grid_frame to expand with window
        self.grid_frame.grid_rowconfigure(0, weight=1)
        self.grid_frame.grid_columnconfigure(0, weight=1)

        # Canvas to hold the actual image labels, allowing scrolling
        self.canvas = tk.Canvas(self.grid_frame, bg="#f0f0f0")
        self.canvas.grid(row=0, column=0, sticky="nsew")

        self.scrollbar = tk.Scrollbar(self.grid_frame, orient="vertical", width=30, command=self.canvas.yview)
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Frame inside canvas to hold the image labels
        self.image_labels_frame = tk.Frame(self.canvas, bg="#f0f0f0")
        # Store the ID of the window created inside the canvas
        self.canvas_window_id = self.canvas.create_window((0, 0), window=self.image_labels_frame, anchor="nw")

        # Bind canvas resize to update the inner frame's width and trigger grid reflow
        self.canvas.bind("<Configure>", self.on_canvas_configure)
        # Bind inner frame configure to update scroll region (its height will change)
        self.image_labels_frame.bind("<Configure>", self.on_frame_configure)

        # --- Buttons Frame ---
        self.button_frame = tk.Frame(master, bd=2, relief="groove")
        self.button_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        # Configure button_frame columns for layout: Delete | (flexible space) | Paste | Close
        self.button_frame.grid_columnconfigure(0, weight=0) # Delete button column
        self.button_frame.grid_columnconfigure(1, weight=1) # Flexible space column
        self.button_frame.grid_columnconfigure(2, weight=0) # Paste button column
        self.button_frame.grid_columnconfigure(3, weight=0) # Close button column


        # Garbage Can / Delete Area
        self.delete_area_label = tk.Label(self.button_frame, text="🗑️ Drag here to Delete",
                                          font=("Inter", 12), bg="#ffcccc", fg="#cc0000",
                                          relief="solid", bd=2, padx=10, pady=5)
        self.delete_area_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")


        self.paste_button = tk.Button(self.button_frame, text="Paste",
                                      command=self.paste_from_clipboard,
                                      font=("Inter", 12), bg="#4CAF50", fg="white",
                                      activebackground="#45a049", relief="raised", bd=3,
                                      padx=10, pady=5)
        self.paste_button.grid(row=0, column=2, padx=5, pady=5, sticky="e") # Placed in new column 2

        self.close_button = tk.Button(self.button_frame, text="Accept",
                                     command=self.close_application,
                                     font=("Inter", 12), bg="#3277d9", fg="white",
                                     activebackground="#3277d9", relief="raised", bd=3,
                                     padx=10, pady=5) # color was bg="#f44336" activebackground="#da190b"
        self.close_button.grid(row=0, column=3, padx=5, pady=5, sticky="w") # Placed in new column 3

        self.redraw_grid() # Initial draw of an empty grid
        
        # load dolphin on initial run
        # read command line to know folder to open in
        #print (f"sys.argv {sys.argv} : {len(sys.argv)}")
        if len(sys.argv) > 1: 
            self.fileBrowser = subprocess.Popen(['flatpak','run','org.kde.dolphin',sys.argv[1]],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True)
        else:
            self.fileBrowser = subprocess.Popen(['flatpak','run','org.kde.dolphin'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True  )  
         
         
        # attempt to move and resize Dolphin (will use the first instance it finds)
        window_title = "Dolphin"
        geometry_string =  str(int(WINDOW_WIDTH_MULTIPLIER * screen_width)+1) + ",0," + str(int(screen_width - WINDOW_WIDTH_MULTIPLIER * screen_width)-1) + "," + str(screen_height)
        global window_id
        try:
            for i in range(1,5):
                # Find the window ID
                result = subprocess.run(['wmctrl', '-l'], capture_output=True, text=True, check=True)
                window_id = None
                for line in result.stdout.splitlines():
                    if window_title in line:
                        window_id = line.split()[0] # Get the first part, which is the ID
                        break
                if window_id:
                    break
                else:
                    time.sleep(1)
            if window_id:
                subprocess.run(['wmctrl', '-ir',window_id, '-e', f'0,{geometry_string}'], check=True)
                #print(f"Resized window '{window_title}' on try {i} to {geometry_string}' (ID: {window_id})")
            else:
                messagebox.showerror("Window with title '{window_title}' not found.")

        except subprocess.CalledProcessError as e:
            messagebox.showerror("Error executing wmctrl: {e}")
        except FileNotFoundError:
            messagebox.showerror("wmctrl command not found. Please ensure it's installed and in your PATH.")
                            
    def on_canvas_configure(self, event):
        """
        Adjusts the width of the inner image_labels_frame to match the canvas width.
        This ensures the grid reflows horizontally.
        """
        # Update the width of the window inside the canvas
        self.canvas.itemconfig(self.canvas_window_id, width=event.width)
        # Update scroll region and trigger redraw if width has changed
        if event.width != self._last_frame_width:
            self._last_frame_width = event.width
            self.redraw_grid()

    def on_frame_configure(self, event):
        """
        Updates the scroll region of the canvas when the inner frame's content changes height.
        """
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))


    def load_thumbnail(self, filepath):
        """
        Loads an image, resizes it to a thumbnail, and returns a PhotoImage.

        Args:
            filepath (str): The full path to the image file.

        Returns:
            ImageTk.PhotoImage or None: The PhotoImage object if successful, None otherwise.
        """
        try:
            if filepath.endswith(".webm") or filepath.endswith(".mp4") :
                script_directory = os.path.dirname(__file__)
                data_file_path = os.path.join(script_directory, "video.png")
                img = Image.open(data_file_path)
            else:
                img = Image.open(filepath)
                                
            img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(img)
        except FileNotFoundError:
            messagebox.showerror("Error: File not found at {filepath}")
            #print(f"Error: File not found at {filepath}")
            return None
        except Exception as e:
            messagebox.showerror("Error loading image {filepath}: {e}")
            #print(f"Error loading image {filepath}: {e}")
            return None

    def add_image_to_grid(self, filepath):
        """
        Adds a new image thumbnail data to the internal list.
        The actual label creation and binding happens in redraw_grid.

        Args:
            filepath (str): The full path to the image file.
        """
        photo = self.load_thumbnail(filepath)
        if photo:
            # Store filename and photo_image. Label will be created/updated in redraw_grid.
            image_info = {
                'filename': filepath,
                'photo_image': photo,
                'label': None # Placeholder, will be set in redraw_grid
            }
            self.images_data.append(image_info)
            self.redraw_grid() # Redraw the entire grid to place the new image

    def redraw_grid(self):
        """
        Clears the current grid and recreates/redraws all thumbnails based on self.images_data.
        This ensures fresh labels are used after reordering or adding images,
        and also handles dynamic column calculation.
        """
        # Clear existing labels from the frame
        for widget in self.image_labels_frame.winfo_children():
            widget.destroy()

        # Calculate dynamic GRID_COLUMNS
        # Add 10 for padx/pady (5 on each side)
        cell_total_width = THUMBNAIL_SIZE[0] + 10
        # Use the canvas's width to determine columns, as the inner frame's width is now tied to it
        frame_width = self.canvas.winfo_width()
        if frame_width == 0: # Handle initial state before canvas has a width
            dynamic_grid_columns = 1
        else:
            dynamic_grid_columns = max(1, frame_width // cell_total_width)

        # Store the current dynamic columns for use in stop_drag
        self.current_grid_columns = dynamic_grid_columns

        # Place labels in the grid
        for i, item in enumerate(self.images_data):
            # Create a NEW label for each item
            label = tk.Label(self.image_labels_frame, image=item['photo_image'], width=THUMBNAIL_SIZE[0], height=THUMBNAIL_SIZE[0], relief="solid", bd=1)
            label.image = item['photo_image'] # Keep a reference to prevent garbage collection

            # Update the 'label' reference in our images_data list
            item['label'] = label

            # Bind drag and drop events to the NEW label
            label.bind("<Button-1>", self.start_drag)
            label.bind("<B1-Motion>", self.do_drag)
            label.bind("<ButtonRelease-1>", self.stop_drag)

            row = i // self.current_grid_columns
            col = i % self.current_grid_columns
            item['label'].grid(row=row, column=col, padx=5, pady=5)

        # Update scroll region after redrawing
        self.image_labels_frame.update_idletasks() # Ensure widgets are placed before calculating bbox
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))


    def start_drag(self, event):
        """
        Starts the drag operation when a thumbnail is clicked.
        """
        # Find which label was clicked
        for item in self.images_data:
            if item['label'] == event.widget:
                self.dragged_item = item
                self.drag_start_x = event.x_root
                self.drag_start_y = event.y_root

                # Store original grid position (for potential future use, though not strictly needed for reorder logic)
                info = item['label'].grid_info()
                self.drag_original_row = info['row']
                self.drag_original_col = info['column']

                # Create a ghost image for visual feedback
                self.ghost_label = tk.Label(self.master, image=item['photo_image'], width=THUMBNAIL_SIZE[0], height=THUMBNAIL_SIZE[0], relief="solid", bd=1, bg="lightgray")
                self.ghost_label.image = item['photo_image'] # Keep reference
                # Place the ghost label relative to the root window, adjusted for mouse click position on the label
                self.ghost_label.place(x=event.x_root - self.master.winfo_x() - event.x,
                                       y=event.y_root - self.master.winfo_y() - event.y)
                break

    def do_drag(self, event):
        """
        Handles the movement of the dragged thumbnail.
        """
        if self.dragged_item:
            # Move the ghost label
            # Calculate new position relative to the master window, maintaining the offset from the initial click
            new_x = event.x_root - self.master.winfo_x() - (self.drag_start_x - self.master.winfo_x() - self.dragged_item['label'].winfo_x())
            new_y = event.y_root - self.master.winfo_y() - (self.drag_start_y - self.master.winfo_y() - self.dragged_item['label'].winfo_y())
            self.ghost_label.place(x=new_x, y=new_y)

    def stop_drag(self, event):
        """
        Ends the drag operation and reorders the thumbnails or deletes them if dropped on the garbage can.
        """
        if self.dragged_item:
            # Destroy the ghost label
            if hasattr(self, 'ghost_label') and self.ghost_label.winfo_exists():
                self.ghost_label.destroy()
                del self.ghost_label

            # Get coordinates of the garbage can area
            delete_x = self.delete_area_label.winfo_rootx()
            delete_y = self.delete_area_label.winfo_rooty()
            delete_width = self.delete_area_label.winfo_width()
            delete_height = self.delete_area_label.winfo_height()

            drop_x = event.x_root
            drop_y = event.y_root

            # Check if the drop occurred over the garbage can
            if (delete_x <= drop_x <= (delete_x + delete_width) and
                delete_y <= drop_y <= (delete_y + delete_height)):
                # Delete the item
                self.images_data.remove(self.dragged_item)
                self.redraw_grid()
                self.dragged_item = None
                # messagebox.showinfo("Image Deleted", "Image successfully removed from the grid.")
                return # Exit function after deletion

            # If not dropped on garbage can, proceed with reordering logic
            # Determine the target cell based on mouse release coordinates
            # Convert root coordinates to coordinates relative to image_labels_frame
            frame_abs_x = self.image_labels_frame.winfo_rootx()
            frame_abs_y = self.image_labels_frame.winfo_rooty()

            relative_x = event.x_root - frame_abs_x
            relative_y = event.y_root - frame_abs_y

            # Calculate target row and column. Add padding into consideration.
            # Assuming padx/pady are 5 on each side, total 10 per cell.
            cell_width = THUMBNAIL_SIZE[0] + 10
            cell_height = THUMBNAIL_SIZE[1] + 10

            target_col = int(relative_x // cell_width)
            target_row = int(relative_y // cell_height)

            # Get the total number of items
            num_items = len(self.images_data)

            # Use the dynamically calculated current_grid_columns
            current_cols = self.current_grid_columns if hasattr(self, 'current_grid_columns') else 1

            # Calculate the effective maximum row and column based on current items
            if num_items > 0:
                max_possible_index = num_items - 1
                max_row_current = max_possible_index // current_cols
                max_col_current = max_possible_index % current_cols
            else:
                max_row_current = 0
                max_col_current = 0

            # Clamp target_row and target_col to valid range
            target_row = max(0, target_row)
            target_col = max(0, target_col)

            # If dropping beyond the last row, clamp to the last row
            if target_row > max_row_current:
                target_row = max_row_current
                target_col = max_col_current # If dropping past the last row, assume drop at the end of the last item

            # If dropping within the last row but past the last item in that row
            elif target_row == max_row_current and target_col > max_col_current:
                target_col = max_col_current

            # Ensure target_col doesn't exceed current_cols for rows that are not the last
            if target_row < max_row_current:
                target_col = min(target_col, current_cols - 1)


            new_index = target_row * current_cols + target_col

            # Ensure new_index is within bounds of existing items
            new_index = min(new_index, num_items - 1)
            new_index = max(0, new_index) # Cannot drop before the first item

            if self.dragged_item:
                original_index = self.images_data.index(self.dragged_item)

                if original_index != new_index:
                    # Reorder the internal list
                    item_to_move = self.images_data.pop(original_index)
                    self.images_data.insert(new_index, item_to_move)
                    self.redraw_grid() # Redraw the grid to reflect the new order

            self.dragged_item = None # Reset dragged item

    def paste_from_clipboard(self):
        """
        Reads filenames from the clipboard using xclip and adds them to the grid.
        """
        try:
            # Use subprocess to run xclip and capture its output
            # -o: output clipboard content
            # -selection clipboard: specifies the clipboard selection (primary is default)
            clipboard_content = subprocess.run(['xclip', '-o', '-selection', 'clipboard'],
                                               capture_output=True, text=True, check=True)
            filenames_raw = clipboard_content.stdout.strip().replace("file://","")

            if not filenames_raw:
                messagebox.showinfo("Clipboard Empty", "No content found in clipboard.")
                return

            # Split filenames by newline. Handle potential multiple paths.
            # Filter out empty strings that might result from multiple newlines.
            potential_filenames = [f.strip() for f in filenames_raw.split('\n') if f.strip()]

            added_count = 0
            for filename in potential_filenames:
                # Basic check if it looks like a file path and exists
                if os.path.exists(filename) and os.path.isfile(filename):
                    # Check if it's an image file (simple extension check)
                    _, ext = os.path.splitext(filename)
                    if ext.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff','.webm','.mp4']:
                        self.add_image_to_grid(filename)
                        added_count += 1
                    #else:
                    #    print(f"Skipping non-image file: {filename}")
                #else:
                #    print(f"Skipping non-existent or non-file path: {filename}")

            if added_count == 0:
                messagebox.showinfo("No Images Added", "No valid image files were found or added from the clipboard.")
            #else:
            #    messagebox.showinfo("Images Added", f"Successfully added {added_count} image(s) from clipboard.")

        except FileNotFoundError:
            messagebox.showerror("Error", "xclip not found. Please install xclip (e.g., sudo apt-get install xclip).")
        except subprocess.CalledProcessError as e:
            messagebox.showerror("Error", f"Failed to read clipboard: {e.stderr}")
        except Exception as e:
            messagebox.showerror("Error", f"An unexpected error occurred: {e}")

    def close_application(self):
        """
        Closes the application and prints the ordered list of filenames.
        """
        
        #close the dolphin browser opened at the beginning
        global window_id
        try:
            subprocess.run(['wmctrl', '-ic',window_id], check=True)
        except Exception as e:
            pass
                
        ordered_filenames = [item['filename'] for item in self.images_data]
        # print("\n--- Final Ordered List of Image Filenames ---")
        for filename in ordered_filenames:
            print(filename)
        # print("---------------------------------------------")

        self.master.destroy() # Close the Tkinter window
    
    def on_closing(self):
        """
        If the user clicked the "X" on the window - then just close and clean up.
        """     
        #close the dolphin browser opened at the beginning
        global window_id
        try:
            subprocess.run(['wmctrl', '-ic',window_id], check=True)
        except Exception as e:
            pass
                                            
        self.master.destroy() # Close the Tkinter window
       
if __name__ == "__main__":
    # Ensure Pillow is installed: pip install Pillow
    # Ensure xclip is installed on your Linux system: sudo apt-get install xclip (for Debian/Ubuntu)

    root = tk.Tk()
    app = ImageGridApp(root)
    root.mainloop()
