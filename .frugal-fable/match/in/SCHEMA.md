# Output schema (one JSON file per batch)

{
  "contests": [
    {
      "contest": "<the '## ...' header line of the contest, verbatim>",
      "questions": [
        {
          "id": "<short slug, unique within the contest, e.g. income-tax-cut>",
          "topic": "<one of: housing cost health taxes energy safety homeless emerg education streets water roads growth community immigration economy environment abortion guns crime jobs agriculture veterans elections budget finance childcare other>",
          "q": {"en": "<ONE neutral policy statement the voter can agree or disagree with, max 110 characters>", "es": "<Spanish translation, same length limit>"},
          "tradeoff": {"en": "<optional, max 90 chars: the cost or counter-consideration of agreeing, stated plainly>", "es": "<Spanish>"},
          "sides": {
            "<candidate name slug: lowercase letters only, e.g. stevehilton>": {"side": 1, "idx": 0, "quote": "<verbatim excerpt (max 120 chars) from statement [idx] that shows this side>"}
          }
        }
      ]
    }
  ]
}

side: 1 = this candidate's documented statement supports AGREEING with q; -1 = supports DISAGREEING.
Omit a candidate from "sides" when none of their statements clearly takes a side. Never guess.
