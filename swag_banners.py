import random

# A collection of punchlines extracted from the project's soul
PUNCHLINES = [
    "OIDA!",
    "BAM!",
    "BIST JETZT!",
    "089 UNDERGROUND",
    "MINGA FLOW",
    "WEISS WURSCHT IS!",
    "S T A D E L H E I M",
    "Bavaria Noir",
    "S Y N A P S E",
    "OIDA SWAG",
    "BETON & BLUT",
    "ISAR SYNDIKAT"
]

BANNERS = [
    # Variant 1: Blocky/Heavy
    """
      ___   ___   ____   ____   ____   _   _  ___   _   _ 
     / _ \\ / _ \\ / ___| / ___| / ___| | | | |/ _ \\ | | | |
    | | | | | | | |  _ | |  _ | |  _  | |_| | | | || |_| |
    | |_| | |_| | |_| || |_| || |_| | |  _  | |_| ||  _  |
     \\___/ \\___/ \\____| \\____| \\____| |_| |_|\\___/ |_| |_|
    """,
    # Variant 2: Cyber/Slant
    """
       ____  ___  ____  ___   ____  _   ___  ____  __  __ 
      / __ \\/ _ \\/ __ \\/   | / ___/ / | / / / __ \\/ / / / 
     / / / / / / / / / / /| \\ \\__ \\ | |/ / / / / / / / /  
    / /_/ / / / / /_/ / /_/ /___/ / |   / / /_/ / / /_/ /   
    \\____/\\_/ /_\\____/ \\____/____/  |_| \\_/ \\____/ \\____/    
    """,
    # Variant 3: Minimalist/Wide
    """
    S Y N A P S E   A U D I O   D Y N A M I C S
    ===========================================
    """,
]

def get_swag_banner():
    banner = random.choice(BANNERS)
    punchline = random.choice(PUNCHLINES)
    
    # Format the punchline to be centered under the banner
    # Roughly calculate center based on the first line of the banner
    if banner:
        first_line_len = len(banner.splitlines()[0]) if banner.splitlines() else 40
        centered_punchline = punchline.center(first_line_len)
    else:
        centered_punchline = punchline

    return f"{banner}\n{centered_punchline}\n"
