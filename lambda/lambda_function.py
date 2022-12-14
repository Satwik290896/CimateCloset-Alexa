import logging
import ask_sdk_core.utils as ask_utils
import json
from ask_sdk_model.interfaces.alexa.presentation.apl import (
    RenderDocumentDirective)
import requests


from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.handler_input import HandlerInput

from ask_sdk_model import Response

import os
import boto3

from ask_sdk_core.skill_builder import CustomSkillBuilder
from ask_sdk.standard import StandardSkillBuilder
from ask_sdk_dynamodb.adapter import DynamoDbAdapter
from ask_sdk_core.dispatch_components import AbstractRequestInterceptor
from ask_sdk_core.dispatch_components import AbstractResponseInterceptor

# are you tracking past celebrities between sessions


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
checking_visits = True


class LoadDataInterceptor(AbstractRequestInterceptor):
    """Check if user is invoking skill for first time and initialize preset."""
    def process(self, handler_input):
        # type: (HandlerInput) -> None
        persistent_attributes = handler_input.attributes_manager.persistent_attributes
        session_attributes = handler_input.attributes_manager.session_attributes

        # ensure important variables are initialized so they're used more easily in handlers.
        # This makes sure they're ready to go and makes the handler code a little more readable

        if 'jackets' not in persistent_attributes:
            persistent_attributes["jackets"] = []

        if 'jackets' not in session_attributes:
            session_attributes["jackets"] = []
            
        if 'visits' not in persistent_attributes:
            persistent_attributes["visits"] = 0

        if 'visits' not in session_attributes:
            session_attributes["visits"] = 0
        
        if 'checking_visits' not in session_attributes:
            session_attributes["checking_visits"] = True
            
        # if you're tracking jackets between sessions, use the persistent value
        # set the visits value (either 0 for new, or the persistent value)
        
        session_attributes["visits"] = persistent_attributes["visits"]
        
        if session_attributes["checking_visits"] == True:
            if (session_attributes["visits"])%5 != 0:
                session_attributes["jackets"] = persistent_attributes["jackets"]
                if len(session_attributes["jackets"]) == 0:
                    session_attributes["visits"] = 0
                    persistent_attributes["visits"] = 0
            else:
                session_attributes["jackets"] = []
                persistent_attributes["jackets"] = []
                session_attributes["visits"] = 0
                persistent_attributes["visits"] = 0

class LoggingRequestInterceptor(AbstractRequestInterceptor):
    """Log the alexa requests."""
    def process(self, handler_input):
        # type: (HandlerInput) -> None
        logger.debug('----- REQUEST -----')
        logger.debug("{}".format(
            handler_input.request_envelope.request))

class SaveDataInterceptor(AbstractResponseInterceptor):
    """Save persistence attributes before sending response to user."""
    def process(self, handler_input, response):
        # type: (HandlerInput, Response) -> None
        persistent_attributes = handler_input.attributes_manager.persistent_attributes
        session_attributes = handler_input.attributes_manager.session_attributes

        persistent_attributes["jackets"] = session_attributes["jackets"]
        persistent_attributes["visits"] = session_attributes["visits"]

        handler_input.attributes_manager.save_persistent_attributes()

class LoggingResponseInterceptor(AbstractResponseInterceptor):
    """Log the alexa responses."""
    def process(self, handler_input, response):
        # type: (HandlerInput, Response) -> None
        logger.debug('----- RESPONSE -----')
        logger.debug("{}".format(response))




class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for Skill Launch."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool

        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        session_attributes = handler_input.attributes_manager.session_attributes
        persistent_attributes = handler_input.attributes_manager.persistent_attributes
        speak_output = ""
        
        if len(session_attributes['jackets']) == 0:
            speak_output = "Please list your jackets from lightest to heaviest."
            session_attributes["visits"] = 0
        else:
            speak_output += "Let's check the coat for your weather. Where are you right now?"

        session_attributes["checking_visits"] = False
        persistent_attributes["visits"] = session_attributes["visits"]
        handler_input.attributes_manager.session_attributes = session_attributes
        handler_input.attributes_manager.persistent_attributes = persistent_attributes
        
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

class GetJacketIntentHandler(AbstractRequestHandler):
    """Handler for Skill Launch."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool

        return (
            ask_utils.is_request_type("IntentRequest")(handler_input)
                and ask_utils.is_intent_name("SaveJacketIntent")(handler_input)
        )

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        session_attributes = handler_input.attributes_manager.session_attributes
        persistent_attributes = handler_input.attributes_manager.persistent_attributes
        
        speak_output = ""
        jacket = ask_utils.request_util.get_slot(handler_input, "jacket").value.split(" ")

        for i in range(0, len(jacket)):
            session_attributes['jackets'].append(jacket[i])


        persistent_attributes['jackets'] = session_attributes['jackets']
        handler_input.attributes_manager.session_attributes = session_attributes
        handler_input.attributes_manager.persistent_attributes = persistent_attributes

        speak_output = "Ok. Let's check the coat for your weather. Where are you right now? You can tell me the city name."


        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )


class JacketChoiceIntent(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("JacketChoiceIntent")(handler_input)
    
    
    def handle(self, handler_input):
        session_attributes = handler_input.attributes_manager.session_attributes
        persistent_attributes = handler_input.attributes_manager.persistent_attributes
        
        api_address = "http://api.openweathermap.org/data/2.5/weather?appid=b0666605b00ec702162e1e7eed44da5d&units=metric&q="
        slots = handler_input.request_envelope.request.intent.slots
        city = slots['city'].value
        speak_output = ''
        url = api_address + city
        json_data = requests.get(url).json()
        formatted_json = json_data['weather'][0]['main']
        temp = json_data['main']['temp']
        name = json_data['name']
        sys = json_data['sys']['country']
        wind = json_data['wind']['speed']
        description = json_data['weather'][0]['description']
        speak_output = "Perfect! you live in {}. ".format(city)
        speak_output += "The weather is {}, {} and temp is {} of {} and the wind speed is {}.".format(formatted_json, description, temp, name, wind)
        generic = " The best jacket would be "
        if temp < 5:
            speak_output += generic + session_attributes["jackets"][-1]
        elif temp>= 5 and temp <= 12 and wind >= 25 and wind <= 40:
            if len(session_attributes["jackets"]) >= 2:
                speak_output += generic + session_attributes["jackets"][-2]
            else:
                speak_output += generic + session_attributes["jackets"][-1]
        elif temp >= 5 and temp <= 12 and wind >= 0 and wind <= 25:
            if len(session_attributes["jackets"]) >= 3:
                speak_output += generic + session_attributes["jackets"][-3]
            elif len(session_attributes["jackets"]) >= 2:
                speak_output += generic + session_attributes["jackets"][-2]
            else:
                speak_output += generic + session_attributes["jackets"][-1]
        elif temp >= 13 and temp <= 25 and wind < 25:
            speak_output += generic + session_attributes["jackets"][0]
        elif temp >= 13 and temp <= 25 and wind >= 25 and wind <= 40:
            if len(session_attributes["jackets"]) >= 3:
                speak_output += generic + session_attributes["jackets"][2]
            elif len(session_attributes["jackets"]) >= 2:
                speak_output += generic + session_attributes["jackets"][1]
            else:
                speak_output += generic + session_attributes["jackets"][0]
        elif temp >= 13 and temp <= 25 and wind >= 25 and wind <= 40:
            if len(session_attributes["jackets"]) >= 2:
                speak_output += generic + session_attributes["jackets"][1]
            else:
                speak_output += generic + session_attributes["jackets"][0]
        elif temp >=  25:
            speak_output += generic + "no jacket, it is quite hot outside"

        session_attributes["visits"] += 1
        persistent_attributes["visits"] = session_attributes["visits"]
        handler_input.attributes_manager.session_attributes = session_attributes
        handler_input.attributes_manager.persistent_attributes = persistent_attributes

        
        return (
            handler_input.response_builder
                .speak(speak_output)
                .response
        )

class HelpIntentHandler(AbstractRequestHandler):
    """Handler for Help Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "You can say hello to me! How can I help?"

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )


class CancelOrStopIntentHandler(AbstractRequestHandler):
    """Single handler for Cancel and Stop Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input) or
                ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "Goodbye!"

        return (
            handler_input.response_builder
                .speak(speak_output)
                .response
        )

class FallbackIntentHandler(AbstractRequestHandler):
    """Single handler for Fallback Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In FallbackIntentHandler")
        speech = "Hmm, I'm not sure. You can say Hello or Help. What would you like to do?"
        reprompt = "I didn't catch that. What can I help you with?"

        return handler_input.response_builder.speak(speech).ask(reprompt).response

class SessionEndedRequestHandler(AbstractRequestHandler):
    """Handler for Session End."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response

        # Any cleanup logic goes here.

        return handler_input.response_builder.response


class IntentReflectorHandler(AbstractRequestHandler):
    """The intent reflector is used for interaction model testing and debugging.
    It will simply repeat the intent the user said. You can create custom handlers
    for your intents by defining them above, then also adding them to the request
    handler chain below.
    """
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("IntentRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        intent_name = ask_utils.get_intent_name(handler_input)
        speak_output = "You just triggered " + intent_name + "."

        return (
            handler_input.response_builder
                .speak(speak_output)
                # .ask("add a reprompt if you want to keep the session open for the user to respond")
                .response
        )

class CatchAllExceptionHandler(AbstractExceptionHandler):
    """Generic error handling to capture any syntax or routing errors. If you receive an error
    stating the request handler chain is not found, you have not implemented a handler for
    the intent being invoked or included it in the skill builder below.
    """
    def can_handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> bool
        return True

    def handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> Response
        logger.error(exception, exc_info=True)

        speak_output = "Sorry, I had trouble doing what you asked. Please try again."

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

# The SkillBuilder object acts as the entry point for your skill, routing all request and response
# payloads to the handlers above. Make sure any new handlers or interceptors you've
# defined are included below. The order matters - they're processed top to bottom.

ddb_region = os.environ.get('DYNAMODB_PERSISTENCE_REGION')
ddb_table_name = os.environ.get('DYNAMODB_PERSISTENCE_TABLE_NAME')

ddb_resource = boto3.resource('dynamodb', region_name=ddb_region)
dynamodb_adapter = DynamoDbAdapter(table_name=ddb_table_name, create_table=False, dynamodb_resource=ddb_resource)

sb = CustomSkillBuilder(persistence_adapter = dynamodb_adapter)


#sb = SkillBuilder()

sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(GetJacketIntentHandler())
sb.add_request_handler(JacketChoiceIntent())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(FallbackIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_request_handler(IntentReflectorHandler()) # make sure IntentReflectorHandler is last so it doesn't override your custom intent handlers

sb.add_exception_handler(CatchAllExceptionHandler())

# Interceptors
sb.add_global_request_interceptor(LoadDataInterceptor())
sb.add_global_request_interceptor(LoggingRequestInterceptor())

sb.add_global_response_interceptor(SaveDataInterceptor())
sb.add_global_response_interceptor(LoggingResponseInterceptor())

lambda_handler = sb.lambda_handler()