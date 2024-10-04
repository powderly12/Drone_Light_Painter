import PySimpleGUI as sg

# Define colors
COLORS = ['Red', 'Green', 'Blue']

# Create the layout
layout = [
    [sg.Canvas(key='-CANVAS-', size=(400, 400), background_color='white')],
    [sg.Text('Choose Color:'), sg.Combo(COLORS, default_value='Red', key='-COLOR-')],
    [sg.Button('Clear'), sg.Button('Exit')]
]

# Create the window
window = sg.Window('Drawing App', layout, finalize=True)

# Access the canvas element
canvas = window['-CANVAS-'].TKCanvas

# Variables to store drawing state
drawing = False
current_color = 'Red'
last_x, last_y = None, None

def draw_line(x1, y1, x2, y2, color):
    canvas.create_line(x1, y1, x2, y2, fill=color, width=2)

# Event loop
while True:
    event, values = window.read(timeout=10)

    if event == sg.WIN_CLOSED or event == 'Exit':
        break

    # Update the current color from the combo box
    if event == '-COLOR-':
        current_color = values['-COLOR-']

    if event == 'Clear':
        canvas.delete('all')  # Clear the canvas

    # Mouse events for drawing
    if event == '-CANVAS-':
        mouse_event = values['-CANVAS-']
        if mouse_event == 'MouseDown':
            drawing = True
            last_x, last_y = window['-CANVAS-'].TKCanvas.winfo_pointerxy()
        elif mouse_event == 'MouseMove' and drawing:
            mouse_x, mouse_y = window['-CANVAS-'].TKCanvas.winfo_pointerxy()
            draw_line(last_x, last_y, mouse_x, mouse_y, current_color)
            last_x, last_y = mouse_x, mouse_y
        elif mouse_event == 'MouseUp':
            drawing = False

# Close the window
window.close()
