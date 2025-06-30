FROM public.ecr.aws/lambda/python:3.11

COPY . ${LAMBDA_TASK_ROOT}

RUN  pip install -r src/requirements.txt --target "${LAMBDA_TASK_ROOT}"
 
CMD [ "src.app.lambda_handler" ]