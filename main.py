from concurrent.futures import ThreadPoolExecutor
import tkinter as tk
import tkinter.messagebox as messagebox
import copy
from datetime import datetime
import argparse
import logging
import os
from typing import Callable, TypedDict, Literal


default_undo_snapshot_size = 5
geometry = "1600x500"
gui_state = "normal"
default_team1_color = "Stripes"
default_team2_color = "Solids"
icon_fname = "00546aecf458d72e9e2c3e9457a14a5f.ico"


current_directory = os.path.dirname(os.path.abspath(__file__))
icon = os.path.join(current_directory, icon_fname)


def calculate_percentage(numerator: float, denominator: float) -> float:
    return (numerator / denominator) * 100 if denominator else 0.0


class TeamStats(TypedDict):
    visits: int
    easy_shots: int
    difficult_shots: int
    safety_shots: int
    break_shots: int
    easy_potted: int
    difficult_potted: int
    safety_potted: int
    break_potted: int
    additional_potted: int
    fouls: int
    foul_only_shots: int


class OverallStats(TypedDict):
    team1: TeamStats
    team2: TeamStats
    total: TeamStats


TeamsLiteral = Literal["team1", "team2"]


StatsLiteral = Literal[
    'visits', 'easy_shots', 'difficult_shots', 'safety_shots', 'break_shots',
    'easy_potted', 'difficult_potted', 'safety_potted', 'break_potted', 'additional_potted', 'fouls'
]


class PoolStatsApp(tk.Tk):

    @staticmethod
    def get_starting_team_stats() -> TeamStats:
        return {
            'visits': 0,
            'easy_shots': 0,
            'easy_potted': 0,
            'difficult_shots': 0,
            'difficult_potted': 0,
            'safety_shots': 0,
            'safety_potted': 0,
            'break_shots': 0,
            'break_potted': 0,
            'additional_potted': 0,
            'fouls': 0,
            'foul_only_shots': 0
        }

    def reset_team_stats(self) -> None:
        # Reset all stats to zero
        self.team_stats["team1"] = self.get_starting_team_stats()
        self.team_stats["team2"] = self.get_starting_team_stats()

    def __init__(self, master=None, undo_snapshot_size: int = default_undo_snapshot_size,
                 google_account_file: str = None, gsheets_sheet_name: str = None):
        super().__init__(master)
        self.iconbitmap(icon)
        self.google_account_file = google_account_file
        self.gsheets_sheet_name = gsheets_sheet_name
        self.undo_snapshot_size = undo_snapshot_size
        self.master = master
        self.title("Pool Game Statistics")
        self.executor = ThreadPoolExecutor()
        self.geometry(geometry)

        self.team_stats: OverallStats = {
            'team1': self.get_starting_team_stats(),
            'team2': self.get_starting_team_stats(),
            'total': self.get_starting_team_stats()
        }
        self.active_team: TeamsLiteral | None = None

        # GUI elements
        self.break_buttons = []
        self.stats_history = []
        self.action_log_history = []
        self.state(gui_state)
        self.setup_ui()
        self.update_stats_display()

        # Initializing the start_time and end_time
        self.start_time: datetime | None = None
        self.end_time: datetime | None = None

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def store_snapshots(self) -> None:
        """Store the current state of stats for undo operation."""
        stats_snapshot = copy.deepcopy(self.team_stats)
        action_log_snapshot = self.action_log.get('1.0', tk.END)
        # Check if length exceeds the limit
        for snapshots in (self.stats_history, self.action_log_history):
            if len(snapshots) >= self.undo_snapshot_size:
                snapshots.pop(0)  # Remove the oldest snapshot
        self.stats_history.append(stats_snapshot)
        self.action_log_history.append(action_log_snapshot)

    def undo(self, btn: tk.Button) -> None:
        """Undo the last recorded action."""
        logging.debug('Undo requested')
        self.provide_button_feedback(btn)

        if self.stats_history:
            current_team_stats = self.team_stats
            self.team_stats = self.stats_history.pop()
            self.update_stats_display(current_team_stats, highlight_changes="italic")
            if self.action_log_history:
                action_log_text = self.action_log_history.pop()
                self.action_log.delete('1.0', tk.END)
                self.action_log.insert(tk.END, action_log_text)
        else:
            messagebox.showwarning("Undo", "Cannot undo anymore!")

    def reset(self, btn: tk.Button) -> None:
        """Reset all stats."""
        logging.debug('Reset requested')
        self.provide_button_feedback(btn)

        result = messagebox.askyesno("Confirmation", "Are you sure you want to reset all stats?")
        if result:
            self.store_snapshots()
            # Reset all stats to zero
            self.reset_team_stats()

            # Re-enable break buttons
            for button in self.break_buttons:
                button.config(state=tk.NORMAL)

            self.start_time = self.end_time = None

            if default_team1_color not in self.team1_label.cget("text"):
                self.toggle_teams_colors()
            self.update_stats_display(highlight_changes="")
            self.action_log.delete("1.0", tk.END)

    def create_button_frame(self, column_index: int, team: TeamsLiteral) -> tk.Frame:
        frame = tk.Frame(self, padx=10, pady=10)
        frame.grid(row=1, column=column_index, padx=5, pady=5)

        buttons_config = [
            ('Difficult shot potted', 'difficult_potted'),
            ('Difficult shot missed', 'difficult_shots'),
            ('Easy shot potted', 'easy_potted'),
            ('Easy shot missed', 'easy_shots'),
            ('Safety unexpected pot', 'safety_potted'),
            ('Safety shot', 'safety_shots'),
            ('Foul Only', 'foul_only_shots'),
            ('Pot Existing Shot', 'additional_potted'),
            ('Foul Existing Shot', 'fouls'),
            ('Break shot potted', 'break_potted'),
            ('Break shot missed', 'break_shots'),
        ]

        for idx, (btn_text, action) in enumerate(buttons_config):
            btn = tk.Button(frame, text=btn_text)
            btn.config(command=lambda btn=btn, action=action: self.record_action(team, action, btn))
            btn.grid(row=idx, column=0, sticky=tk.W + tk.E, pady=2)

            # Storing reference to the break buttons
            if "break" in action:
                self.break_buttons.append(btn)

        return frame

    def create_stats_text_widget(self, column_index: int) -> tk.Text:
        widget = tk.Text(self, height=17, width=30)
        widget.grid(row=1, column=column_index, padx=5, pady=5)
        widget.config(state=tk.DISABLED)
        return widget

    def add_action_button(self, text: str, row: int, column: int, callback: Callable[[tk.Button], None]) -> None:
        btn = tk.Button(self, text=text)
        btn.configure(command=lambda btn=btn: callback(btn))
        btn.grid(row=row, column=column, pady=20)

    def add_action(self, text: str, append: bool = False) -> None:
        if append:
            self.action_log.insert('1.end', f', {text}')
        else:
            current_time = datetime.now().strftime('%H:%M:%S')
            message = f'{current_time}: {text}\n'
            self.action_log.insert('1.0', message)
        self.action_log.see('1.0')

    def setup_ui(self) -> None:
        # Team 1 Buttons
        self.team1_frame = self.create_button_frame(column_index=0, team='team1')

        # Team 1 Stats
        self.team1_stats_text = self.create_stats_text_widget(column_index=1)

        # Total Stats
        self.total_stats_text = self.create_stats_text_widget(column_index=2)

        # Team 2 Stats
        self.team2_stats_text = self.create_stats_text_widget(column_index=3)

        # Team 2 Buttons
        self.team2_frame = self.create_button_frame(column_index=4, team='team2')

        # Headings for each section
        self.team1_label = tk.Label(self, text=f"Team 1 ({default_team1_color})", font=("Arial", 16))
        self.team1_label.grid(row=0, column=0, pady=5)
        tk.Label(self, text="Team 1 Stats", font=("Arial", 16)).grid(row=0, column=1, pady=5)
        tk.Label(self, text="Total Stats", font=("Arial", 16)).grid(row=0, column=2, pady=5)
        tk.Label(self, text="Team 2 Stats", font=("Arial", 16)).grid(row=0, column=3, pady=5)
        self.team2_label = tk.Label(self, text=f"Team 2 ({default_team2_color})", font=("Arial", 16))
        self.team2_label.grid(row=0, column=4, pady=5)

        # Adjust the rows of frames and text widgets to be below the headings
        self.team1_frame.grid(row=1, column=0, padx=5, pady=5)  # Adjusted the row to 1
        self.team1_stats_text.grid(row=1, column=1, padx=5, pady=5)  # Adjusted the row to 1
        self.total_stats_text.grid(row=1, column=2, padx=5, pady=5)  # Adjusted the row to 1
        self.team2_stats_text.grid(row=1, column=3, padx=5, pady=5)  # Adjusted the row to 1
        self.team2_frame.grid(row=1, column=4, padx=5, pady=5)  # Adjusted the row to 1

        self.add_action_button("Undo", 2, 0, self.undo)
        self.add_action_button("Toggle Colors", 2, 1, self.toggle_teams)
        self.add_action_button("Complete Game", 2, 2, self.complete_game)
        self.add_action_button("Export Stats", 2, 3, self.export_stats)
        self.add_action_button("Reset", 2, 4, self.reset)

        # Add the new Text widget for action logging along the bottom
        self.action_log_label = tk.Label(self, text="Actions", font=("Arial", 16))
        self.action_log_label.grid(row=0, column=5, pady=5, sticky='nw')  # Span the entire width

        self.action_log = tk.Text(self, wrap=tk.NONE, width=60, height=20)  # Adjust width/height as needed
        self.action_log.grid(row=1, rowspan=3, column=5, padx=5, pady=5, sticky='nsew')  # Span the entire width

        # Create a vertical scrollbar
        self.action_log_scrollbar = tk.Scrollbar(self, orient=tk.VERTICAL, command=self.action_log.yview)
        self.action_log_scrollbar.grid(row=1, column=6, rowspan=2, sticky='nsew')

        self.action_log.config(yscrollcommand=self.action_log_scrollbar.set)

    def toggle_teams_colors(self, reset: bool = False):
        # Check the current label text for Team 1
        if reset or default_team1_color not in self.team1_label.cget("text"):
            self.team1_label.config(text=f"Team 1 ({default_team1_color})")
            self.team2_label.config(text=f"Team 2 ({default_team2_color})")
        else:
            self.team1_label.config(text=f"Team 1 ({default_team2_color})")
            self.team2_label.config(text=f"Team 2 ({default_team1_color})")

    def toggle_teams(self, btn: tk.Button):
        self.provide_button_feedback(btn)
        self.toggle_teams_colors()

    def complete_game(self, btn: tk.Button):
        self.provide_button_feedback(btn)
        self.end_time = datetime.now()
        logging.debug('Game completed')
        self.add_action("Game complete")
        self.update_stats_display()

    def provide_button_feedback(self, btn: tk.Button):
        # Provide feedback
        original_color = btn.cget("background")
        btn.config(bg="blue")  # Change the button color to green temporarily
        self.after(300, lambda: btn.config(bg=original_color))  # Restore original color after 300ms

    def record_action(self, team: TeamsLiteral, action: str, btn: tk.Button):
        self.provide_button_feedback(btn)

        team_name = team.replace("team", "Team ")
        action_name = action.replace("_", " ").replace("potted", "ball potted").replace(
            "shots", "shot").replace( 'foul only shot', 'Foul').replace(
            'fouls', 'Foul').capitalize()
        if action_name.endswith('shot'):
            action_name = f'{action_name} missed'
        message = f"{team_name} {action_name}"
        logging.debug('')
        logging.debug("%s %s", team_name, action_name)

        if "break" in action and self.team_stats[team]['break_shots'] > 0:
            messagebox.showerror("Error", "Only one break shot allowed!")
            return

        # Set the start time if it's a break shot and start time is not set
        if "break" in action and not self.start_time:
            self.start_time = datetime.now()
            # Disable both break buttons if a break shot is recorded
            for break_btn in self.break_buttons:
                break_btn.config(state=tk.DISABLED)

        self.store_snapshots()

        if any(text == action for text in ("additional_potted", "fouls")):
            self.add_action(action_name, append=True)
        else:
            self.add_action(message, append=False)

        if self.active_team != team:
            self.active_team = team
            self.team_stats[team]['visits'] += 1

        if action in ['difficult_potted', 'easy_potted', 'safety_potted', 'break_potted']:
            shot_type = action.split('_')[0]
            self.team_stats[team][f"{shot_type}_shots"] += 1

        if action == 'foul_only_shots':
            self.team_stats[team]['fouls'] += 1

        self.team_stats[team][action] += 1
        self.update_stats_display()

    @staticmethod
    def generate_stats_text(stats: TeamStats, prev_stats: TeamStats, name: str = "",
                            highlight_changes: str = "bold") -> list[tuple[str, str]]:
        total_pot_attempts = stats['easy_shots'] + stats['difficult_shots']
        total_shots = stats['easy_shots'] + stats['difficult_shots'] + stats['safety_shots'] + stats[
            'break_shots'] + stats['foul_only_shots']
        total_potted = stats['easy_potted'] + stats['difficult_potted']
        total_potted_with_break = total_potted + stats['break_potted']
        total_pots_with_additional = total_potted_with_break + stats['safety_potted'] + stats['additional_potted']

        shot_percent = calculate_percentage(total_pots_with_additional, total_shots)
        pot_percent = calculate_percentage(total_potted, total_pot_attempts)
        pot_per_visit = total_pots_with_additional / (stats['visits'] or 1)
        easy_shot_percent = calculate_percentage(stats['easy_potted'], stats['easy_shots'])
        difficult_shot_percent = calculate_percentage(stats['difficult_potted'], stats['difficult_shots'])

        text = []
        k: StatsLiteral
        for k, v in stats.items():
            key_name = k.replace('_', ' ').capitalize()
            if (prev_value := prev_stats[k]) == v:
                tag = ""
            else:
                if name:
                    logging.debug("%s %s changed from %s to %s", name, key_name, prev_value, v)
                tag = highlight_changes
            if not k == "foul_only_shots":
                text.append((tag, f"{key_name}: {v}"))

        text.append(("", f"Total shots: {total_shots}"))
        text.append(("", f"Pot %: {pot_percent:.2f}"))
        text.append(("", f"Shot %: {shot_percent:.2f}"))
        text.append(("", f"Easy shot %: {easy_shot_percent:.2f}"))
        text.append(("", f"Difficult shot %: {difficult_shot_percent:.2f}"))
        text.append(("", f"Pot/visit: {pot_per_visit:.2f}"))
        text.append(("", ""))

        return text

    def update_stats_display(self, prev_stats: OverallStats = None, highlight_changes: str = "bold") -> None:
        if not prev_stats:
            prev_stats = self.stats_history[-1] if self.stats_history else self.team_stats

        team1_stats_text = self.generate_stats_text(self.team_stats['team1'], prev_stats['team1'], "Team 1",
                                                    highlight_changes=highlight_changes)
        self.update_text_widget(self.team1_stats_text, team1_stats_text)

        team2_stats_text = self.generate_stats_text(self.team_stats['team2'], prev_stats['team2'], "Team 2",
                                                    highlight_changes=highlight_changes)
        self.update_text_widget(self.team2_stats_text, team2_stats_text)

        k: StatsLiteral
        for k in self.team_stats['team1']:
            self.team_stats['total'][k] = self.team_stats['team1'][k] + self.team_stats['team2'][k]

        total_stats_text = self.generate_stats_text(self.team_stats['total'], prev_stats['total'],
                                                    highlight_changes=highlight_changes)
        self.update_text_widget(self.total_stats_text, total_stats_text)

    def update_text_widget(self, widget: tk.Text, text: list[tuple[str, str]]):
        widget.config(state=tk.NORMAL)
        widget.delete(1.0, tk.END)
        for tag, line in text:
            line = line + "\n"
            if tag:
                widget.insert(tk.END, line, tag)
            else:
                widget.insert(tk.END, line)
        widget.config(state=tk.DISABLED)
        widget.tag_configure('bold', font=('TkDefaultFont', 10, 'bold'))
        widget.tag_configure('italic', font=('TkDefaultFont', 10, 'italic'))

    def upload_to_gsheets(self, data: list[str]) -> str:
        import gspread
        gc = gspread.service_account(self.google_account_file)
        spreadsheet = gc.open(self.gsheets_sheet_name)
        worksheet = spreadsheet.get_worksheet(0)
        if first_empty_row_in_column_a := worksheet.find("", in_column=1):
            row = first_empty_row_in_column_a.row
            worksheet.update(f'A{row}:Z{row}', [data])
            return f"Team 1 and Team 2 Stats have been inserted into Google Sheets {self.gsheets_sheet_name} first sheet row {row}!"
        worksheet.append_row(data)
        return f"Team 1 and Team 2 Stats have been appended to Google Sheets {self.gsheets_sheet_name} first sheet!"

    def export_stats(self, btn: tk.Button):
        self.provide_button_feedback(btn)
        # Extracting the stats in order and converting to a tab-delimited string
        stats_order = [
            'visits', 'easy_shots', 'easy_potted', 'difficult_shots', 'difficult_potted',
            'safety_shots', 'safety_potted', 'break_shots', 'break_potted', 'additional_potted',
            'fouls', 'foul_only_shots'
        ]

        stat: StatsLiteral
        team1_stats = [self.team_stats['team1'][stat] for stat in stats_order]
        team2_stats = [self.team_stats['team2'][stat] for stat in stats_order]

        # Extracting start and end times
        self.end_time = self.end_time or datetime.now()
        start_time_str = self.start_time.strftime("%Y-%m-%d %H:%M:%S") if self.start_time else 'N/A'
        end_time_str = self.end_time.strftime("%Y-%m-%d %H:%M:%S") if self.end_time else 'N/A'

        data = [start_time_str, end_time_str] + team1_stats + team2_stats

        if self.google_account_file and self.gsheets_sheet_name:
            fut = self.executor.submit(self.upload_to_gsheets, data)
            fut.add_done_callback(lambda future: messagebox.showinfo("Exported", future.result()))
        else:
            export_string = '\t'.join(list(map(str, data)))
            # Using the clipboard to copy the export string for easy pasting
            self.clipboard_clear()
            self.clipboard_append(export_string)
            self.update()  # This is to make sure the clipboard is updated immediately
            message = "Team 1 and Team 2 Stats have been copied to clipboard for pasting into a spreadsheet!"
            messagebox.showinfo("Exported", message)

    def on_closing(self):
        # Shutdown the thread pool executor
        self.executor.shutdown(wait=True)
        # Destroy the window
        self.destroy()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A tool for tracking pool stats")

    parser.add_argument("-u", "--undo-snapshot-size", type=int, default=default_undo_snapshot_size,
                        help="Size of the undo snapshot (integer value).")

    parser.add_argument("--log-level", type=str, choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        default='DEBUG', help="Set the logging level.")

    parser.add_argument("--google-account-file", type=str,
                        help="Path to a google service account .json file for uploading data to Google Sheets.")

    parser.add_argument("--gsheets-sheet_name", type=str,
                        help="Name of a Google Sheets spreadsheet.")

    args = parser.parse_args()

    logging.basicConfig(level=args.log_level,
                        format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

    app = PoolStatsApp(undo_snapshot_size=args.undo_snapshot_size,
                       google_account_file=args.google_account_file,
                       gsheets_sheet_name=args.gsheets_sheet_name)
    app.mainloop()
