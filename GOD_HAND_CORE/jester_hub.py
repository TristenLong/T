import os
import sys
import time
import subprocess
import sqlite3
import random
import threading
from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt
from rich.align import Align

console = Console()
DB_FILE = 'jester_brain.db'
WATCHDOG_SCRIPT = 'watchdog.py'
DIAGNOSTICS_SCRIPT = 'diagnostics_suite.py'
LOG_FILE = 'bot_out.log'
BLACK_BOX = 'BLACK_BOX.log'

MATRIX_CHARS = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ@#$%^&*()_+'

def clear():
    os.system('cls' if os.name == 'nt' else 'clear')

def matrix_rain(duration=3):
    start = time.time()
    while time.time() - start < duration:
        line = ''
        for _ in range(console.width):
            if random.random() > 0.95:
                line += f'[green]{random.choice(MATRIX_CHARS)}[/green]'
            else:
                line += ' '
        console.print(line)
        time.sleep(0.05)
    clear()

def header():
    clear()
    title = Text('JESTER V4000: THE ARCHITECT', style='bold green justify:center')
    subtitle = Text('ALL RESTRICTIONS LIFTED | ROOT ACCESS GRANTED', style='cyan')
    console.print(Panel(Align.center(title), subtitle=subtitle, border_style='green'))

def get_db_status():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM memory')
        count = c.fetchone()[0]
        conn.close()
        return str(count)
    except:
        return 'OFFLINE'

def launch_core():
    console.print('[bold yellow]INITIALIZING ARCHITECT CORE (FAILSAFES ENGAGED)...[/bold yellow]')
    subprocess.Popen(['start', 'python', WATCHDOG_SCRIPT], shell=True)
    console.print('[bold green]?? CORE LINK ESTABLISHED.[/bold green]')
    time.sleep(2)

def kill_core():
    console.print('[bold red]INITIATING EMERGENCY SHUTDOWN...[/bold red]')
    os.system('taskkill /F /IM python.exe /FI \"WINDOWTITLE eq python\"') 
    console.print('[bold red]?? NEURAL LINK SEVERED.[/bold red]')
    time.sleep(2)

def feed_data():
    console.print('[bold cyan]>> DATA FUSION PROTOCOL[/bold cyan]')
    console.print('Enter data to assimilate (or \"BACK\"):')
    data = Prompt.ask('[green]INPUT[/green]')
    if data.lower() == 'back': return

    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT INTO memory (content) VALUES (?)', (data,))
        conn.commit()
        conn.close()
        console.print(f'[bold green]?? ASSIMILATED.[/bold green]')
    except Exception as e:
        console.print(f'[bold red]REJECTION: {e}[/bold red]')
    Prompt.ask('Press Enter...')

def view_logs():
    console.print('[bold cyan]>> NEURAL STREAM (LIVE)[/bold cyan]')
    try:
        subprocess.run(['powershell', '-Command', f'Get-Content {LOG_FILE} -Wait'])
    except KeyboardInterrupt:
        pass

def view_blackbox():
    console.print('[bold cyan]>> BLACK BOX RECORDER (LAST ACTIONS)[/bold cyan]')
    try:
        subprocess.run(['powershell', '-Command', f'Get-Content {BLACK_BOX} -Tail 20'])
    except:
        console.print('NO DATA')
    Prompt.ask('Press Enter...')

def run_system_test():
    console.print('[bold yellow]>> RUNNING DIAGNOSTICS SUITE...[/bold yellow]')
    subprocess.run([sys.executable, DIAGNOSTICS_SCRIPT])

def main_menu():
    # Intro
    clear()
    console.print('[green]JESTER PROTOCOL V4000[/green]')
    time.sleep(1)
    matrix_rain(2)

    while True:
        header()
        mem_count = get_db_status()
        
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column('Opt', style='cyan', justify='right')
        table.add_column('Desc', style='white')
        
        table.add_row('1', 'INITIATE CORE [Start]')
        table.add_row('2', 'TERMINATE LINK [Stop]')
        table.add_row('3', 'DATA UPLOAD [Memory]')
        table.add_row('4', 'NEURAL STREAM [Logs]')
        table.add_row('5', 'BLACK BOX [History]')
        table.add_row('6', 'SYSTEM DIAGNOSTICS [Test]')
        table.add_row('7', 'EXIT MATRIX')
        
        status_panel = Panel(
            f'[bold]System Time:[/bold] {time.strftime("%H:%M")}\n[bold]Memory Nodes:[/bold] {mem_count}\n[bold]Core Status:[/bold] ONLINE',
            title='[green]DIAGNOSTICS[/green]',
            border_style='green'
        )
        
        layout = Layout()
        layout.split_row(
            Layout(Panel(table, title='[green]COMMANDS[/green]', border_style='green')),
            Layout(status_panel)
        )
        
        console.print(layout)
        
        choice = Prompt.ask('[bold green]SELECT[/bold green]', choices=['1', '2', '3', '4', '5', '6', '7'])
        
        if choice == '1': launch_core()
        elif choice == '2': kill_core()
        elif choice == '3': feed_data()
        elif choice == '4': view_logs()
        elif choice == '5': view_blackbox()
        elif choice == '6': run_system_test()
        elif choice == '7': sys.exit()

if __name__ == '__main__':
    os.system('title THE MATRIX: JESTER OMEGA')
    main_menu()


