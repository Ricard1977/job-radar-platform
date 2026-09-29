import unittest
from ai.cleanup_candidates import build_cleanup_candidates

class CleanupCandidatesTest(unittest.TestCase):
    def test_partitions_without_automatic_actions(self):
        decisions=[
            {"job_id":1,"action":"ELIMINAR","confidence":0.96,"pattern":"SAP","reason":"Rol funcional SAP"},
            {"job_id":2,"action":"ELIMINAR","confidence":0.72,"pattern":"Cloud","reason":"Caso ambiguo"},
            {"job_id":3,"action":"MANTENER","confidence":0.99,"pattern":"","reason":"Buen encaje"},
            {"job_id":999,"action":"ELIMINAR","confidence":0.99,"pattern":"x","reason":"fuera del lote"},
        ]
        result=build_cleanup_candidates(decisions,{1,2,3})
        self.assertEqual([1],[x["job_id"] for x in result["probable_irrelevant"]])
        self.assertEqual([2],[x["job_id"] for x in result["doubtful"]])
        self.assertEqual(2,result["candidate_count"])
        self.assertEqual(0,result["automatic_actions"])

    def test_single_negative_is_not_a_global_rule(self):
        decisions=[{"job_id":7,"action":"MANTENER","confidence":0.4,"pattern":"engineer","reason":"Ambiguo"}]
        result=build_cleanup_candidates(decisions,{7})
        self.assertEqual(0,result["candidate_count"])

if __name__=="__main__":
    unittest.main()
