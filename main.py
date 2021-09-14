from datetime import datetime, timedelta
import os
import tkinter as tk

import pandas as pd
from pandas.core.frame import DataFrame
from pandas.core.series import Series
from PIL import Image, ImageTk

months = [
    'January',
    'February',
    'March',
    'April',
    'May',
    'June',
    'July',
    'August',
    'September',
    'October',
    'November',
    'December'
]


def output(frame: tk.Frame, message: str, color='white') -> None:
    print(message)
    frame.message_label['fg'] = color
    frame.message_label['text'] = message


def handle_error(frame: tk.Frame, str: str) -> None:
    output(frame, str)
    quit()


def log(str: str, log_list: list) -> list:
    """Appends a timestamped str to log_list"""
    
    log_list.append(f'[{datetime.now().isoformat()}] {str}')
    return log_list


def get_repeat_num(head: str, list: list) -> str:
    """Calculates modifier for head such that it is unique in list"""

    add = ['', 0]
    while head + add[0] in list:
        add[1] += 1
        add[0] = f' ({add[1]})'
    return head + add[0]


def write_session(log_list: list, ses_df: DataFrame, ses_names: list[str]) -> None:
    """Writes the log and csv output files specified by the given data"""

    #Handling for logs
    log_path = make_abs_time_dir('files\\logs', 'txt', ses_names)
    with open(log_path, mode='w', encoding='UTF-8') as f:
        f.writelines(log_list)
    
    #Handling for tables
    #Formats ses_df (session_dataframe) for output
    ses_df_copy = ses_df.copy()
    ses_df_copy['Credit'] = ses_df['Credit'].astype(int)
    ses_df_copy['Times'] = ses_df['Times'].apply(
        lambda x: [str(e) for e in x]
    )
    ses_df_copy['Total Time'] = ses_df_copy['Total Time'].map(
        timedelta.total_seconds
    )
    ses_df_copy['Total Time'] /= 3600
    ses_df_copy = ses_df_copy.rename(
        columns={
            'Total Time': 'Hours Spent'
        }
    )
    #Writes modified copy of ses_df
    table_path = make_abs_time_dir('files\\tables', 'csv', ses_names)
    ses_df_copy.to_csv(table_path)


def make_abs_time_dir(rel_path: str, ext: str, names: list) -> str:
    """
    Calculates file name (so there is no conflict within names), 
    and creates directories leading up to the file name
    """
    now = datetime.now()

    out_dir = f'{os.getcwd()}\\{rel_path}\\{now.year}\\{months[now.month - 1]}'

    #Creates output_directory if it doesn't already exist
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    #Output file name with relative directory
    return f'{out_dir}\\{get_repeat_num(str(now.day), names)}.{ext}'


def sort_key(series: Series) -> Series:
    """Attendance sorting algorithm"""

    #For the grade column, sort new members last (True sorts after False)
    if series.name == 'Grade':
        return series == 9

    #For 'Full Name', sort alphabetically by last, then first name
    string = series.str
    return string[:string.find(' ')] + string[string.find(' ') + 1:]


def sort_members(member_df: DataFrame) -> DataFrame:
    """Sorts member_df using defined key 'sort_key'"""

    try:
        return member_df.sort_values(['Grade', 'Full Name'], key=sort_key)
    except KeyError:
        handle_error('The "Member List" file was improperly formatted')


def get_members() -> DataFrame:
    """Returns a dataframe of the data in local 'Member List.csv'"""

    try:
        return pd.read_csv(os.getcwd() + '\\Member List.csv').set_index('ID')
    except FileNotFoundError:
        handle_error('The "Member List" file has either been removed or renamed')


def get_output_table() -> DataFrame:
    """
    Returns dataframe of data in local 'Output Table.csv'

    If no file exists, creates one and returns a base dataframe
    """

    file_path = os.getcwd() + '\\Output Table.csv'
    
    #If the file exists
    if os.path.isfile(file_path):
        try:
            return pd.read_csv(file_path).set_index('ID')
        #If file is empty, continue and return base dataframe
        except pd.errors.EmptyDataError as err:
            pass
    
    #If either the file does not exist or the file is empty
    open(file_path, 'w').close()
    return get_members().drop(columns=['Grade'])


def format_output_table(
        csv_df: DataFrame, 
        member_df: DataFrame
    ) -> DataFrame:
    """Returns a properly formatted csv_table"""

    #Technically a one-liner
    #First, merges csv_table and member_table such that:
    #   Members removed from member_table are removed
    #   Members added to member_table are added
    #Next, adds a new column for this session and populates with False
    return pd.merge(
        csv_df, 
        member_df.drop(columns=['Grade']),
        how='right', 
        on=['ID', 'Full Name']
    ).assign(
        **{
            get_repeat_num(
                datetime.now().isoformat()[:10], 
                csv_df.columns
            ): [False] * len(csv_df)
        }
    )


def format_session_table(member_df: DataFrame) -> DataFrame:
    """Returns a new session table instance"""

    ses = member_df.copy()
    #Columns with names and data value functions
    cols = [
        ['Times', list],
        ['Total Time', timedelta],
        ['Credit', lambda: False],
    ]
    #Adds and populates columns
    for name, val in cols:
        ses[name] = [val() for _ in range(len(member_df))]
    
    return ses


def read_cfgs() -> dict:
    """Returns a config dictionary from local 'configs.cfg'"""

    cfg_file_name = 'config.cfg'
    #Default configs
    cfg_dict = {
        'requiredHours': 2
    }

    try:
        with open(cfg_file_name, encoding='UTF-8') as cfg_file:
            for line in cfg_file.readlines():
                if line.find('=') != -1:
                    #For valid lines in 'config.cfg' with an '='
                    opt, val = line.replace('\n', '').split('=', 1)
                    #Try to convert the value (after '=') to a number
                    try:
                        val = eval(val)
                    except NameError:
                        pass
                    except SyntaxError:
                        pass
                    #If it's not a number, just add as string
                    cfg_dict[opt] = val
    #If config.cfg doesn't exist, create it
    except FileNotFoundError:
        open('config.cfg', mode='x', encoding='UTF-8').close()
    
    return cfg_dict


def sign_in_out(ID: int, session_df: DataFrame, reqd_hours: int) -> bool:
    """
    Modifies session_df as necessary for sign-ins and outs and logs.
    
    Saves current time to ID's 'Times' array.
    If it's a sign out, updates time spent at meeting.
    Returns True if event is a sign-in, False if sign-out.
    """

    #Add now to the list of times signed in/out
    session_df.at[ID, 'Times'] += [datetime.now()]

    time_list = session_df.at[ID, 'Times']
    #If event is a sign out
    if not (len(time_list) % 2):
        #Adds timedelta to total time
        session_df.at[ID, 'Total Time'] += time_list[-1] - time_list[-2]
        #Updates credit if timedelta total is enough
        session_df.at[ID, 'Credit'] = \
            session_df\
                .at[ID, 'Total Time']\
                .total_seconds() \
             > reqd_hours * 3600
        
        return False
    return True


def handle_input(frame: tk.Frame, ID: int) -> None:
    #Reset text input field
    frame.ID_input_field.delete(0, len(frame.ID_input_field.get()))
    
    #Uses sign_in_out output to determine sign-in or sign-out
    io = not sign_in_out(ID, frame.ses, frame.cfgs['requiredHours'])
    io = ['in', 'out'][int(io)]
    
    output(frame, f'You have successfully signed {io}!', frame.fg_color)
    log(f'{ID} signed {io}', frame.log_list)


class AttendanceGUI(tk.Frame):
    """
    Creates, manages, and handles GUI;
    Handles input conditional flow
    """

    def __init__(self, root=None, size_factor=1) -> None:
        """
        Initializes frame with data objects, frame widgets, and application window
        """

        #Initialize all dataframes and log list
        self.mem = sort_members(get_members())
        self.out = format_output_table(get_output_table(), self.mem)
        self.ses = format_session_table(self.mem)
        self.cfgs = read_cfgs()
        self.log_list = []

        #Foreground and background colors
        if self.cfgs['backgroundColor'] not in ('black', 'white'):
            raise ValueError('Color present in config file not acceptable')
        self.bg_color = self.cfgs['backgroundColor']
        self.fg_color = 'black' if self.bg_color == 'white' else 'white'

        #GUI initialization/creation
        super().__init__(root)
        self.root = root
        self.root['bg'] = self.bg_color
        self.pack()
        
        #Window formatting
        self.root.title('Attendance')
        self.root.iconbitmap(f'{os.getcwd()}\\images\\logo.ico')

        #Create/initialize widgets
        #Object container (to center all objects in frame)
        self.main_frame = tk.Frame(self.root, background=self.bg_color)
        self.main_frame.pack(expand=True)

        #Logo
        self.logo = ImageTk.PhotoImage(Image.open('images\\logo.png'))
        self.logo_label = tk.Label(
            self.main_frame, 
            image=self.logo, 
            background=self.bg_color
        )
        self.logo_label.grid(column=0, row=0, columnspan=2)
        
        #Input box
        self.ID_input_field = tk.Entry(
            self.main_frame,
            background=self.bg_color,
            foreground=self.fg_color,
        )
        self.ID_input_field.grid(column=0, row=1, sticky='ew')
        
        #Confirm button
        self.confirm_button = tk.Button(
            self.main_frame, 
            text='Enter', 
            command=self.button_pressed,
            background=self.bg_color,
            foreground=self.fg_color,
        )
        self.confirm_button.grid(column=1, row=1, sticky='ew')

        #Label for output messages
        self.message_label = tk.Label(
            self.main_frame,
            text='',
            background=self.bg_color,
            foreground=self.fg_color,
        )
        self.message_label.grid(column=0, row=2, columnspan=2)

        #Set handle_exit to run once window is closed
        self.root.protocol('WM_DELETE_WINDOW', self.handle_exit)
        self.ID_input_field.bind('<Return>', self.button_pressed)

    def button_pressed(self, *args) -> None:
        """
        Called whenever the enter key is pressed

        Evaluates ID interpretation logic and 
        manages handling of signing in/out
        """

        ID = self.ID_input_field.get()
        
        try:
            ID = int(ID)
        except ValueError:
            output(self, f'{ID} cannot be interpreted as an ID number, please try something different', 'red')
            return

        if ID not in self.mem.index:
            output(self, f'{ID} not found in the Member List, please try again', 'red')
            return
        
        handle_input(self, ID)
    
    def handle_exit(self) -> None:
        """
        Run when the program is quit

        Stores all relevant data
        """

        #Converts 'Credit' column from boolean to int for convenience
        self.out[self.out.columns[-1]] = self.ses['Credit'].astype(int)

        #Writes final outputs
        session_names = [n[8:] for n in self.out.columns][2:]
        write_session(self.log_list, self.ses, session_names)
        self.out.to_csv('Output Table.csv')

        log('session ended', self.log_list)

        self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    GUI = AttendanceGUI(root=root)
    GUI.mainloop()