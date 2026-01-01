from django import forms

class LoginForm(forms.Form):
    email = forms.EmailField()
    mot_de_pass = forms.CharField(widget=forms.PasswordInput)
