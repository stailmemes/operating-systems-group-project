# i want colored shell text to help differentiate the types of inputs and outputs for users, instead of
# defining the color every time, this file will be for pre-defining the inputs and handling them.

def errorPrint(text):
    print('\033[93m' +text)

def CInput(text):
    inputed_text = input('\033[95m' + text)
    str(inputed_text)
    return inputed_text