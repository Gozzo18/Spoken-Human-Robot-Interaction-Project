import speech_recognition as sr
import os
from pycorenlp.corenlp import StanfordCoreNLP
import random
from gtts import gTTS
from itertools import izip
from difflib import SequenceMatcher


host = "http://localhost"
port = "9000"
nlp = StanfordCoreNLP(host + ":" + port)


beginning = True
main = False
end = False
can_order = False
reservation = False

history = []
quantities = []
order_number = -1

request_verbs = ['order','bring', 'have', 'prefer', 'bring', 'like','love','get']
opinion_verbs = ['recommend', 'suggest', 'propose','mention','advise']
food_price = [3.50, 2.00, 1.00, 5.00, 5.50, 4.50, 3.00, 2.50, 1.50, 1.75, 7.50, 0.90, 0.50, 2.50, 9.50, 2.50]
menu_nouns = ['pasta', 'rice', 'bread', 'fish', 'steak','ham', 'chicken', 'meatball', 'egg', 'hamburger', 'pizza', 'cheese', 'salad', 'fruit','pie','cupcake']
drink_price = [1.00, 5.50, 3.50, 1.50]
drink_nouns  = ['water','wine','beer','coke']
generic_nouns = ['table','menu','reservation']
finish_nouns = ['bill','invoice', 'account','statement','payment','pay']
reservation_name = ['Riccardo', 'Daniele','Roberto','Mario','Stefano','Franceso','Carlo','Alessio','Michele']

#Iterate over two elements at the item on a list
def pairwise(iterable):
    a = iter(iterable)
    return izip(a, a)

#gTTS speake
def speak(Text):
    tts = gTTS(text=Text, lang='en')
    tts.save("audio.mp3")
    os.system("mpg321 audio.mp3")

#Compute the bill at the end
def compute_bill():
    cont = 0
    amount = 0
    for food in history[:-1]:
        index = menu_nouns.index(food)
        amount +=  food_price[index] * quantities[cont]
        cont += 1
    return amount

#Print the menu
def print_menu():
    euro = unichr(8364)
    for f, m in zip(menu_nouns, food_price):
        print("{:<10} {:<1.2f} {:}".format(f.title(),m,euro.encode('utf-8')))
    for a, b in zip(drink_nouns, drink_price):
        print("{:<10} {:<1.2f} {:}".format(a.title(),b,euro.encode('utf-8')))

#Find all the verbs in the phrase
def find_verbs(POS,Lemmas,root):
    v = []
    start_loc = -1 #Used for find multiple VB tags

    #Find the verbs in the phrase
    for verb in POS:       
        if 'VB' in verb:
            index_of_Lemmas = POS.index(verb,start_loc+1) # Get the index of the VB tag
            #If the root is equal to one of the lemmas which is a verb, we found the main verb of the phrase
            if root == Lemmas[index_of_Lemmas]:
                v = root
                return v     
            #If the verbs if 'please', then is a request
            #elif Lemmas[index_of_Lemmas] == 'please':
            #    request = True
            else:
                #The root is something else, but we still have a verb
                v = Lemmas[index_of_Lemmas]
                start_loc = index_of_Lemmas
    if not v:
        #If no verbs has been found, assume is one of the request_verbs
        v = random.choice(request_verbs)
    return v

#Find the object of the phrase
def find_objects():
    temp = []
    objects = []
    quantity = 1
    file = open("transcript.txt",'r')
    for line in file:
        if line.strip() == 'Constituency parse:':  #Reach the line of the file with title Dependency Parse
            break
    # Reads text until the end of the block:
    for line in file:  # Restart reading the file from the previous line 
        if line == '\n': #If a line is completely empty, we have finished to parse the dependency
            break
        #Parse the text
        if 'NP' in line:
            row = filter(None,line.split(" "))[1:]
            if row:
                for element in row:
                    temp.append(element.replace("(","").replace(")","").replace('\n',''))
    for tag,noun in pairwise(temp):
        if tag == 'NN' or tag == 'NNS':
            noun = noun[0].lower() + noun[1:]
            if noun.endswith('s'):
                noun = noun[:-1]
            if noun in menu_nouns or noun in generic_nouns or noun in finish_nouns or noun in drink_nouns:
                objects.append(noun)
        elif tag =='CD':
            quantity = noun
    if len(objects) > 1:
        quantity = 100
    return objects[0], quantity

#Find the subject of the phrase
def find_subject(dependency,root,Token):
    global command
    global opinion
    subject = None
    #Check the nsubj dependency if present
    for label in dependency:
        if label in 'nsubj' and root in ((((dependency['nsubj'])[0]).split("-"))[0]).lower():
            subject = ((((dependency['nsubj'])[1]).split('-'))[0]).lower()
    #If not present, check if the phrase has a token that is a personal pronoun
    if subject == None:
        for token in Token:
            if 'i' == token.lower() :
                subject = 'You'
                command = True
            elif 'you' == token.lower() :
                subject = 'I'
                opinion = True
            elif 'she' == token.lower():
                subject = 'Madame'
                command = True
            elif 'he' == token.lower():
                subject = 'Sir'
                commnad = True           
            else:
                subject = 'You'
                command = True
    #If nsubj is not null, check if is a personal pronoun
    if not subject == 'i' or not subject == 'you' or not subject == 'she' or not subject == 'he' or not subject == 'we':
        subject = 'you'

    return subject

#Parse the output file text obtained by stanford CoreNLP, get POS-tags, Tokens and Lemmas
def morpho_syntactic_analysis():
    Tokens = []
    POS = []
    Lemmas = []

    file = open('transcript.txt','r')
    for line in file:
        strings = line.split(" ")
        if 'Text' in strings[0]:
            token = strings[0].split("=")
            Tokens.append(token[1])
            for s in strings:
                if 'PartOfSpeech' in s:
                    pos = s.split("=")
                    POS.append(pos[1])
                if 'Lemma' in s:
                    lemma = s.split("=")
                    Lemmas.append(lemma[1])
    file.close()

    return Tokens, POS, Lemmas

#Parse the output file text obtained by Stanford CoreNLP, get dependencies relationships
def extract_dependencies():
    cont = 1
    #Dictionary where the key is the label, the value is an array that contain the head (first element) and the dependent (second element) or the dependency relation
    dependencies = dict()
    file = open("transcript.txt",'r')
    for line in file:
        if line.strip() == 'Dependency Parse (enhanced plus plus dependencies):':  #Reach the line of the file with title Dependency Parse
            break
    # Reads text until the end of the block:
    for line in file:  # Restart reading the file from the previous line 
        if line == '\n': #If a line is completely empty, we have finished to parse the dependency
            break
        #Split the row in label + head, dependent
        row = line.split(",")
        #Get the label and the head
        label = (row[0].split("("))[0]
        head = (row[0].split("("))[1]
        #Get the dependent
        dependent = row[1].replace(")","").strip()
        #If a dependency is already present, change it's name to label + cont
        if label in dependencies:
            label += str(cont)
            dependencies[label] = [head, dependent]
            cont += 1
        else:
            dependencies[label] = [head, dependent]
    file.close()
    return dependencies

#Extract name in case of reservation
def extract_ner():
    ner = ""
    file = open("transcript.txt",'r')
    for line in file:
        if line.strip() == 'Extracted the following NER entity mentions:':  #Reach the line of the file with title NER
            break
    for line in file:  # Restart reading the file from the previous line 
        if line == '\n': #If a line is completely empty, we have finished to parse the dependency
            break
        row = line.replace('\t'," ").replace("\n","").split(" ")
        if row[1].strip() == 'PERSON':
            ner = row[0].strip()
    return ner

#Wait for a confirm of the order from the user
def get_confirmation():
    answered = False
    while not answered :
        #Get the audio
        r = sr.Recognizer()
        with sr.Microphone() as source:
            print('You can confirm now')
            audio = r.listen(source)
        try:
            #ASR
            value = r.recognize_google(audio)
            #Transform output in correct format
            text = format(value).encode("utf-8")
            answered = True
        except sr.UnknownValueError:
            speak("Sorry, I didn't hear you ")
    return text

#Special cases that should be handle differently
def check_special_cases(Lemmas):
    global can_order

    specialCase = False
    for word in Lemmas:
        if (word in menu_nouns or word in drink_nouns) and not can_order:
            speak("You are not able to order yet, ask for a table first")
            specialCase = True
        elif word == 'and':
            speak('I can only handle one order at a time, try again please')
            specialCase = True
        elif word == 'yes' or word == 'no':
            speak("I didn't ask for a confirmation, please try again")
            specialCase = True
    return specialCase

#Generate the answer that the waiter should produce
def generate_answer(subject,verbs,object1,quantity,Tokens):
    answer = 'Sorry, can you please repeat?' #Basic answer in case the phrase was not understood
    request = False
    unpolite_request = False
    command = False  
    opinion = False

    global history
    global quantities
    global order_number
    global reservation 


    #If quantity is 100, more than one things at a time has been ordered
    if quantity == 100:
        answer = ("I can only handle one order at a time, try again please")
        return answer
    if object1.endswith('s'):
        itemOrdered = object1[:-1]
    else:
        itemOrdered = object1
   
    #Check if it is an order
    if 'please' in Tokens:
        command = True
        request = True
    else:
    #If 'please' was not found, check for unpolitely
        if verbs:
            if verbs in Tokens:
                unpolite_request = True
                command = True
        else:
            unpolite_request = True
            command = True
    #Check if asking for opinion
    for verb in opinion_verbs:
        if verb in Tokens:
            opinion = True
    
    #If food was requested
    if itemOrdered in menu_nouns:
        #Check if it is a command
        if command:
            #Ask for confirmation
            if quantity > 1:
                answer = subject + " ordered " + str(quantity) + ' dishes of ' + object1 + ", is that correct?"
            else:
                answer = subject + " ordered a dish of " + object1 + ", is that correct?"
            history.append(object1)
            try:
                quantities.append(int(quantity))
            except ValueError:
                if quantity == 'one':
                    quantities.append(1)
                elif quantity == 'two':
                    quantities.append(2)
                elif quantity == 'three':
                    quantities.append(3)
                elif quantity == 'four':
                    quantities.append(4)

            order_number += 1
            #if confirm():
        elif opinion:
            random = random.choice(menu_nouns)
            answer = subject + " will " + random.choice(opinion_verbs) + " to order " + random
            history.append(random)
            order_number += 1
    elif itemOrdered in drink_nouns:
    	if command:
    		answer = subject + " ordered a bottle of " + object1 + ", is that correct?"

    elif object1 == 'table':
        answer = subject + " said a " + object1 + " for " + str(quantity) + ", is that correct?"
    elif object1 == 'reservation':
        answer = search_reservation()
        reservation = True
    elif object1 == 'menu':
        answer = "This is the menu: "
    #If bill was requested
    elif itemOrdered in finish_nouns:
        answer = "You want me to bring you the bill, is that correct?"
        history.append(itemOrdered)
        order_number += 1
    return answer

#Main part of the scenario
def main_dialogue(dependency,Tokens,POS,Lemmas):
    #Get the root of the phrase
    root = (((dependency['root'])[1]).split('-'))[0]
    #Get the nsubj of the phrase based on the root
    subject = find_subject(dependency,root,Tokens)
    #Find all the verbs of the phrase
    verbs = find_verbs(POS,Lemmas,root)
    #Get the objects of the phrase
    try:
        object1,quantity = find_objects()
    except UnboundLocalError:
        answer = "Sorry, I didn't catch what you were saying"
        return answer
    except IndexError:
        answer = "Sorry, I didn't catch what you were saying"
        return answer
    
    answer = generate_answer(subject,verbs,object1,quantity,Tokens)

    return answer

def search_reservation():
    answer = "Sorry, can you please repeat?"
    speak("Can you please give me your name?")
    get_speach()
    NER = extract_ner()
    if NER == "":
        answer = "There is no reservation with that name, I'm sorry"
    else:
        for person in reservation_name:
            ratio = SequenceMatcher(a=NER,b=person).ratio()
            if ratio > 0.5:
                name = person
            answer = "Found it. Follow me " + name
    if name == "":
        answer = "There is no reservation with that name, I'm sorry"
    return answer      

def get_speach():
    speaking = True
    while speaking:
        try:
            #Get the audio
            r = sr.Recognizer()
            with sr.Microphone() as source:
                r.adjust_for_ambient_noise(source, duration=1)
                print('You can start speaking')
                audio = r.listen(source)
            try:
                #ASR
                value = r.recognize_google(audio)
                #Transform output in correct format
                text = format(value).encode("utf-8")
                #Dependency parser
                output = nlp.annotate(
                    text,
                    properties={
                        "outputFormat" : "text",
                        "annotators" : "tokenize,depparse,entitymentions,sentiment"
                    }
                )
                print(output)
                #Save the output as a txt file
                transcript = open("transcript.txt", "w")
                transcript.write(output)
                transcript.close()
                speaking = False
            except sr.UnknownValueError:
                speak("Sorry, I didn't hear you ")
        except KeyboardInterrupt:
            pass

#Core part of the programm
def core():
    global main
    global finish_nouns
    global beginning
    global reservation

    get_speach()
    #Extract Tokens and their pos-tagging 
    Tokens, POS, Lemmas = morpho_syntactic_analysis()
    print(Lemmas)
    #Check special cases
    if check_special_cases(Lemmas):
        return False # A special case has been found, exit the method and try again
    #Extract dependencies
    dependency = extract_dependencies()
    #Generate answer
    answer = main_dialogue(dependency,Tokens,POS,Lemmas)
    speak(answer)
    if 'menu' in answer:
        print_menu()
        return False
    if 'Found it' in answer:
        reservation = True 
        return True
    elif answer == "There is no reservation with that name, I'm sorry":
        return False
    if answer == 'Sorry, can you please repeat?' or answer ==  "Sorry, I didn't catch what you were saying":
        return False #Retry
    else:
        #Get confirmation
        value = get_confirmation()
        #For the first part
        if 'yes' in value:
            if beginning : #If we are in the presentation phase
                speaking = False #Disable the initial condition so we will not have an infinite loop looking for audio
                beginning = False
                #if reservation:
                #    search_reservation()
                #    if answer == "There is no reservation with that name, I'm sorry":
                #        reservation = False
                #        return False
                return True
            elif main : #We are not in the beginning phase but in the main, so we are ordering things                            
                concluded = False
                for fin in finish_nouns:
                    if fin in Tokens: #If a bill or a synonims has been requested, we transition to the end phase
                        speaking = False
                        main = False
                        concluded = True
                        return concluded
                answer = "I'm going to bring your order as soon as possible " 
                speak(answer)
                return concluded
        elif 'no' in value:
            if reservation:
                reservation = False
            speak("Sorry, can you please repeat then?")

#Main
if __name__ == "__main__":
    finished = False
    presented = False

    while not finished:
        if beginning:
            if not presented:
                speak("Welcome to the Mc Ale brother's restaurant, how can I help you?")
                print("ASK FOR A RESERVATION OR FOR A TABLE")
                presented = True
            next_phase = core()
            if next_phase == True:
                can_order = True
                main = True
                if reservation:
                    print("You can now order food, this is the menu:")
                    print_menu()
                else:
                    speak("Let me check first")
                    speak("We have what your are looking for, follow me")
                    print("You can now order food, this is the menu:")
                    print_menu()
        elif main:
            next_phase = core()
            if next_phase and not main:
                speak("I'm going to bring you the bill")
                money = compute_bill()
                speak("You have to pay an amount of " + str(money) + " euro")
                main = False
                end = True
        elif end:
            print("You paid the bill")
            speak('I hope you enjoyed our dishes, thank you and goodbye!')
            end = False
            finished = True
