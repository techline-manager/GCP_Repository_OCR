from flask import Flask, request, jsonify
from google.oauth2 import service_account
import google.auth.transport.requests
import base64
import requests

from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "🚀 FastAPI is running!"}

