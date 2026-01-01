from django import forms

class MemoireCreateForm(forms.Form):
    titre = forms.CharField(max_length=255)
    type = forms.ChoiceField(choices=[("PFE","PFE"),("MEMOIRE","MEMOIRE"),("RAPPORT","RAPPORT"),("THESE","THESE")])
    description = forms.CharField(widget=forms.Textarea, required=False)

    id_etudiant = forms.IntegerField()
    id_annee = forms.IntegerField()

    fichier_pdf = forms.FileField(required=False)
