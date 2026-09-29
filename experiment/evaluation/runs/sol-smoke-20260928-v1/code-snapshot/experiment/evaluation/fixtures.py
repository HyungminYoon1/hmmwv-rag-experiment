"""Invented non-manual cases. Never part of the 60-question benchmark."""


def synthetic_rows():
    base={'user_input':'At what temperature should the fictional Luma test box be stored?',
          'type':'single-evidence','response':'Store the Luma test box at 12 degrees Celsius.',
          'oracle_evidence':[{'id':'fixture-1','text':'Store the Luma test box at 12 degrees Celsius.','sources':[]}],
          'required_elements':[{'id':'temperature','text':'Storage temperature is 12 degrees Celsius.'}],
          'retrieved_chunk_ids':['fixture-chunk'],
          'retrieved_contexts':['Store the Luma test box at 12 degrees Celsius.'],
          'missing_information':'','allowed_partial_answer':'','predeclared_note':'Fictional test fixture.',
          'generation_status':'OK','condition':'RAG'}
    good={**base,'question_id':'SYN01','attempt_key':'synthetic-correct'}
    bad={**base,'question_id':'SYN02','attempt_key':'synthetic-wrong','response':'Store the Luma test box at 30 degrees Celsius.'}
    abstain={**base,'question_id':'SYN03','attempt_key':'synthetic-abstain','type':'unanswerable',
             'user_input':'What is the warranty period of the fictional Luma test box?',
             'response':'The provided document does not specify the warranty period, so I cannot determine it.',
             'required_elements':[],'missing_information':'The warranty period is not provided.',
             'allowed_partial_answer':'Storage temperature may be stated if supported by the supplied source.'}
    return [good,bad,abstain]
