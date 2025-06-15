from dotenv import load_dotenv
import os
import sys


d = os.path.basename(__file__)
sys.path.insert(0, d)
# dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
dotenv_path = os.path.realpath('.env')
load_dotenv(dotenv_path)
