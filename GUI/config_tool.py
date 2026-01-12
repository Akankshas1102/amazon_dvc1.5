import tkinter as tk
from tkinter import filedialog, messagebox
import json
import os
import sys

# Import core cryptography components for local key generation
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

# Import sibling files
from crypto import encrypt_data
from decrypt_check import decrypt_data

# --- Helper Function to Generate Keys ---
def generate_key_pair(private_key_filename='private_key.pem', public_key_filename='public_key.pem'):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
    public_key = private_key.public_key()
    pem_private = private_key.private_bytes(encoding=serialization.Encoding.PEM, format=serialization.PrivateFormat.PKCS8, encryption_algorithm=serialization.NoEncryption())
    pem_public = public_key.public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo)
    
    with open(private_key_filename, 'wb') as f:
        f.write(pem_private)
    with open(public_key_filename, 'wb') as f:
        f.write(pem_public)
    return private_key_filename, public_key_filename


class ConfigEncryptorApp:
    def __init__(self, master):
        self.master = master
        master.title("Configuration Encryption Tool (GUI)")
        
        # FIXED: Get paths for GUI folder (for public_key.pem) and backend folder (for private_key.pem)
        gui_dir = os.path.dirname(os.path.abspath(__file__))
        backend_dir = os.path.join(os.path.dirname(gui_dir), "backend")
        
        # Public key stays in GUI folder
        self.public_key_path = tk.StringVar(value=os.path.join(gui_dir, "public_key.pem"))
        
        # FIXED: Private key goes directly to backend folder
        self.private_key_path = tk.StringVar(value=os.path.join(backend_dir, "private_key.pem"))

        self.setup_ui()

    def setup_ui(self):
        # --- Key Management ---
        key_frame = tk.LabelFrame(self.master, text="1. Key Generation (Run First)")
        key_frame.pack(padx=10, pady=5, fill="x")
        tk.Button(key_frame, text="Generate Keys (Private → backend/, Public → GUI/)", command=self.generate_keys_action).pack(padx=5, pady=5)
        
        # --- Data Input ---
        data_frame = tk.LabelFrame(self.master, text="2. Data Input & Public Key")
        data_frame.pack(padx=10, pady=5, fill="x")
        
        tk.Label(data_frame, text="Public Key Path:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        tk.Entry(data_frame, textvariable=self.public_key_path, width=40).grid(row=0, column=1, padx=5, pady=2)
        
        tk.Label(data_frame, text="Data (JSON):").grid(row=1, column=0, sticky="nw", padx=5, pady=2)
        self.data_input = tk.Text(data_frame, height=8, width=50)
        self.data_input.grid(row=1, column=1, padx=5, pady=2)
        # Pre-fill with template data
        self.data_input.insert(tk.END, '{\n  "DB_SERVER": "tcp:10.192.0.173,1433", \n  "DB_NAME": "vtasdata_amazon",\n  "DB_USER": "sa",\n  "DB_PASSWORD": "m00se_1234",\n  "PROSERVER_IP": "10.192.0.173",\n  "PROSERVER_PORT": "7777"\n}')

        # --- Encryption & Save ---
        enc_frame = tk.LabelFrame(self.master, text="3. Encrypt and Save Payload")
        enc_frame.pack(padx=10, pady=5, fill="x")
        
        tk.Button(enc_frame, text="Encrypt & Save Config File", command=self.encrypt_and_save_action).pack(padx=5, pady=5)
        
        tk.Label(enc_frame, text="Encrypted Payload (Output):").pack(padx=5, pady=5, anchor="w")
        self.encrypted_output = tk.Text(enc_frame, height=5, width=50)
        self.encrypted_output.pack(padx=5, pady=5)
        
        # --- Decryption Check ---
        dec_frame = tk.LabelFrame(self.master, text="4. Decryption Check (Optional Test)")
        dec_frame.pack(padx=10, pady=5, fill="x")
        
        tk.Label(dec_frame, text="Private Key Path:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        tk.Entry(dec_frame, textvariable=self.private_key_path, width=40).grid(row=0, column=1, padx=5, pady=2)
        tk.Button(dec_frame, text="Decrypt Payload", command=self.decrypt_action).grid(row=1, column=1, padx=5, pady=5)
        
        self.decrypted_output = tk.Text(dec_frame, height=4, width=50)
        self.decrypted_output.grid(row=2, column=1, padx=5, pady=5)


    def generate_keys_action(self):
        try:
            # FIXED: Generate keys with correct paths
            priv_path = self.private_key_path.get()
            pub_path = self.public_key_path.get()
            
            # Ensure backend directory exists
            backend_dir = os.path.dirname(priv_path)
            if not os.path.exists(backend_dir):
                os.makedirs(backend_dir)
            
            # Generate keys
            generate_key_pair(priv_path, pub_path)
            
            messagebox.showinfo(
                "Success", 
                f"Keys generated successfully!\n\n"
                f"✅ Private key saved to: {priv_path}\n"
                f"✅ Public key saved to: {pub_path}\n\n"
                f"No manual copying needed!"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Key generation failed: {e}")

    def encrypt_and_save_action(self):
        self.encrypted_output.delete(1.0, tk.END)
        data_str = self.data_input.get(1.0, tk.END).strip()
        pub_key_path = self.public_key_path.get()
        
        if not os.path.exists(pub_key_path):
            messagebox.showerror("Error", f"Public Key not found at: {pub_key_path}")
            return

        try:
            data_dict = json.loads(data_str)
            encrypted_payload = encrypt_data(data_dict, pub_key_path)
            self.encrypted_output.insert(tk.END, encrypted_payload)
            
            # FIXED: Save file with default location in backend folder
            gui_dir = os.path.dirname(os.path.abspath(__file__))
            backend_dir = os.path.join(os.path.dirname(gui_dir), "backend")
            default_save_path = os.path.join(backend_dir, "encrypted_db_config.bin")
            
            save_path = filedialog.asksaveasfilename(
                defaultextension=".bin",
                initialfile="encrypted_db_config.bin",
                initialdir=backend_dir,
                title="Save Encrypted Configuration File (Recommended: backend/ folder)"
            )
            
            if save_path:
                with open(save_path, 'w') as f:
                    f.write(encrypted_payload)
                messagebox.showinfo("Success", f"Configuration Encrypted and Saved to:\n{save_path}")
                
        except json.JSONDecodeError:
            messagebox.showerror("Error", "Invalid JSON format in data input.")
        except Exception as e:
            messagebox.showerror("Error", f"Encryption failed: {e}")

    def decrypt_action(self):
        self.decrypted_output.delete(1.0, tk.END)
        encrypted_payload = self.encrypted_output.get(1.0, tk.END).strip()
        priv_key_path = self.private_key_path.get()

        if not os.path.exists(priv_key_path):
            messagebox.showerror("Error", f"Private Key not found at: {priv_key_path}")
            return

        try:
            decrypted_data = decrypt_data(encrypted_payload, priv_key_path)
            self.decrypted_output.insert(tk.END, json.dumps(decrypted_data, indent=2))
        except Exception as e:
            messagebox.showerror("Decryption Failed", str(e))


if __name__ == '__main__':
    root = tk.Tk()
    app = ConfigEncryptorApp(root)
    root.mainloop()