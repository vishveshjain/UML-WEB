import graphviz
import re
import os
import uuid # To generate unique filenames
from flask import Flask, render_template, request, url_for, flash

app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/' # Needed for flash messages (optional)

# --- Configuration ---
# Directory where generated images will be saved (relative to static folder)
IMAGE_SUBDIR = 'images'
# Full path to the static directory
STATIC_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
# Full path to the image storage directory
IMAGE_SAVE_PATH = os.path.join(STATIC_FOLDER, IMAGE_SUBDIR)

# Ensure the image save directory exists
os.makedirs(IMAGE_SAVE_PATH, exist_ok=True)


# --- Parsing Functions (Copied from previous correct version) ---
def split_ascii_diagrams(ascii_uml):
    """Splits side-by-side ASCII diagrams into separate strings."""
    lines = ascii_uml.strip().splitlines()
    if not lines:
        return []
    separator_indices = []
    if len(lines) > 1:
        potential_seps = [match.start() for match in re.finditer(r'\s{2,}', lines[0])]
        for sep_idx in potential_seps:
            is_consistent_sep = True
            for line in lines[1:]:
                 if len(line) > sep_idx and not line[sep_idx:sep_idx+2].isspace(): pass
            next_char_idx = -1
            if len(lines[0]) > sep_idx:
                match_next = re.search(r'\S', lines[0][sep_idx:])
                if match_next: next_char_idx = sep_idx + match_next.start()
            if next_char_idx != -1: separator_indices.append((sep_idx, next_char_idx))
    separator_indices.sort()
    diagram_strings = []
    start_col = 0
    for sep_end, next_start in separator_indices:
        col_lines = [line[start_col:sep_end].rstrip() for line in lines]
        diagram_strings.append("\n".join(col_lines))
        start_col = next_start
    col_lines = [line[start_col:].rstrip() for line in lines]
    diagram_strings.append("\n".join(col_lines))
    return [s for s in diagram_strings if s.strip()]

def parse_single_class_ascii(class_ascii):
    """Parses a single block of ASCII representing one class diagram."""
    current_class = {}
    lines = class_ascii.strip().splitlines()
    section = 'name'; name_found = False
    for line_num, line in enumerate(lines):
        line = line.strip()
        if not line: continue
        if re.match(r"^\+\-+?\+$", line):
            if name_found and section == 'name': section = 'attributes'; current_class['attributes']=[]; current_class['methods']=[]
            elif section == 'attributes': section = 'methods'
            continue
        if line.startswith('|') and line.endswith('|'):
            content = line[1:-1].strip()
            if not name_found:
                 if content: current_class['name'] = content; name_found = True
            elif section == 'attributes':
                 if content: current_class.setdefault('attributes', []).append(content)
            elif section == 'methods':
                 if content: current_class.setdefault('methods', []).append(content)
    return current_class if name_found else None
# --- End of Parsing Functions ---


# --- UML Generation Logic ---
def generate_uml_image(classes, output_filename_base):
    """Generates the UML PNG image using graphviz."""
    if not classes:
         return None, "No valid classes found to render."

    dot = graphviz.Digraph('UML', comment='UML Class Diagram', format='png')
    dot.attr('node', shape='rectangle')

    for cls in classes:
        cls.setdefault('attributes', [])
        cls.setdefault('methods', [])
        node_label = f"<<TABLE BORDER='0' CELLBORDER='1' CELLSPACING='0'>\n"
        node_label += f"<TR><TD BGCOLOR='lightblue'>{graphviz.escape(cls.get('name', 'Unnamed'))}</TD></TR>\n"
        node_label += f"<TR><TD ALIGN='LEFT'>"
        for attr in cls['attributes']: node_label += f"{graphviz.escape(attr)}<BR/>"
        node_label += "</TD></TR>\n"
        node_label += f"<TR><TD ALIGN='LEFT'>"
        for method in cls['methods']: node_label += f"{graphviz.escape(method)}<BR/>"
        node_label += "</TD></TR>\n"
        node_label += "</TABLE>>"
        node_id = cls.get('name', f'Unnamed_{id(cls)}')
        dot.node(node_id, label=node_label)

    # Save the file inside the static/images directory
    output_filepath_base = os.path.join(IMAGE_SAVE_PATH, output_filename_base)
    print(f"Attempting to render Graphviz to: {output_filepath_base}")

    try:
        # Don't use view=True on a server! Use cleanup=True.
        rendered_path = dot.render(output_filepath_base, view=False, cleanup=True)
        print(f"Graphviz successfully rendered: {rendered_path}")
        # Return the filename part only, relative to the IMAGE_SUBDIR
        return f"{output_filename_base}.png", None
    except graphviz.backend.execute.ExecutableNotFound as e:
        error_msg = f"Graphviz executable not found: {e}. Ensure Graphviz is installed and in PATH."
        print(f"ERROR: {error_msg}")
        return None, error_msg
    except Exception as e:
        error_msg = f"Error during UML image rendering: {e}"
        print(f"ERROR: {error_msg}")
        return None, error_msg


# --- Flask Routes ---
@app.route('/', methods=['GET'])
def index():
    """Display the main page with the input form."""
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    """Handle form submission, parse ASCII, generate UML, display result."""
    ascii_text = request.form.get('ascii_text', '')
    image_filename = None
    error_message = None

    if not ascii_text.strip():
        error_message = "Please paste some ASCII UML text."
    else:
        try:
            diagram_strings = split_ascii_diagrams(ascii_text)
            classes = []
            for class_ascii in diagram_strings:
                parsed_class = parse_single_class_ascii(class_ascii)
                if parsed_class:
                    classes.append(parsed_class)

            if not classes:
                error_message = "Could not parse any valid class diagrams from the input."
            else:
                # Generate a unique base filename to avoid collisions
                unique_id = uuid.uuid4()
                output_filename_base = f"uml_{unique_id}"
                # Generate the image
                image_filename, error_message = generate_uml_image(classes, output_filename_base)

        except Exception as e:
            print(f"ERROR during parsing or splitting: {e}")
            error_message = f"An unexpected error occurred: {e}"

    # Render the same template, passing back data
    return render_template('index.html',
                           ascii_text=ascii_text,
                           image_filename=image_filename,
                           error=error_message)

# --- Run the App ---
if __name__ == '__main__':
    # Use 0.0.0.0 to make it accessible on your network, default port 5000
    # debug=True is helpful for development but disable for production
    app.run(host='0.0.0.0', port=5000, debug=True)