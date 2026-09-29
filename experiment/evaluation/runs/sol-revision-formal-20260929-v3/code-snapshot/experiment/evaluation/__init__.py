"""Post-collection scoring; never imports or reruns the generation pipeline."""
import os

os.environ['RAGAS_DO_NOT_TRACK'] = 'true'
os.environ['LANGSMITH_TRACING'] = 'false'
os.environ['LANGCHAIN_TRACING_V2'] = 'false'

