import customtkinter as ctk

app = ctk.CTk()
ctk.set_appearance_mode("Light")
app.title("Тест Копирки")
app.geometry("400x300")

label = ctk.CTkLabel(app, text="Если вы это видите - CustomTkinter работает!")
label.pack(pady=40)

btn = ctk.CTkButton(app, text="Нажми меня")
btn.pack(pady=10)

app.mainloop()
