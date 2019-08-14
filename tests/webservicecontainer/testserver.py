#!/usr/bin/env python

from bottle import route, run, HTTPError
import pika

EXCHANGE='test'

@route('/<message>')
def index(message):
    import pika

    connection = pika.BlockingConnection(pika.ConnectionParameters(
        host='rabbitmq',
    ))
    channel = connection.channel()

    channel.exchange_declare(
        exchange=EXCHANGE,
        exchange_type='topic',
    )

    channel.queue_declare(queue='message')

    channel.queue_bind(
        queue='message',
        exchange=EXCHANGE,
        routing_key='#',
    )

    channel.basic_publish(
        exchange=EXCHANGE,
        routing_key='hello',
        body=message,
    )

    method_frame, _, message_body = channel.basic_get(
        queue='message',
        no_ack=True,
    )
    if not method_frame or method_frame.NAME == 'Basic.GetEmpty':
        raise HTTPError(500)

    return message_body

run(host='0.0.0.0', port=8080)
