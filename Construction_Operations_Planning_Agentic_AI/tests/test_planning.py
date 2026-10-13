import copy
import json
import random
import tempfile
import unittest
from pathlib import Path
from app.activity_manager import ActivityManager, ValidationError
from app.coordinator import AgenticCoordinator
from app.storage import ProjectRepository, ConflictError
from app.service import ApplicationService, ROOT
from app.reporting import ReportExporter


def project():
    return {'name':'Test site','location':'Chennai','start_date':'2026-10-12','budget':100000,
            'overhead_per_day':100,'target_days':30,'strategy':'critical','data_source':'Test fixture',
            'resources':[{'id':'crew','name':'Crew','kind':'labour','unit':'workers','capacity':4,'rate':100}],
            'tasks':[task('A',2,2),task('B',3,2,['A'])]}


def task(tid,duration,crew,deps=None):
    return {'id':tid,'name':tid,'duration':duration,'dependencies':deps or [],'requirements':{'crew':crew},'priority':3}


def assert_invariants(test, plan):
    p = plan['project']
    rows = {t['id']:t for t in plan['tasks']}
    for t in rows.values():
        if t['status'] == 'blocked':
            continue
        test.assertGreaterEqual(t['start'], t['release_day'])
        test.assertEqual(t['finish']-t['start'],t['duration'])
        for dep in t['dependencies']:
            test.assertEqual(rows[dep]['status'],'scheduled')
            test.assertGreaterEqual(t['start'],rows[dep]['finish'])
    for r in p['resources']:
        if r['kind']=='material':
            events = {t['start'] for t in rows.values() if t['start'] is not None}
            for day in events:
                supply = r['stock'] + sum(d['quantity'] for d in r['deliveries'] if d['day'] <= day)
                used = sum(t['requirements'].get(r['id'],0) for t in rows.values() if t['start'] is not None and t['start']<=day)
                test.assertLessEqual(used,supply+1e-8)
        else:
            for day in range(plan['summary']['duration']):
                use=sum(t['requirements'].get(r['id'],0) for t in rows.values() if t['start'] is not None and t['start']<=day<t['finish'])
                capacity=0 if day in r['unavailable_days'] else r['capacity']
                test.assertLessEqual(use,capacity)


class PlanningTests(unittest.TestCase):
    def setUp(self):
        self.engine=AgenticCoordinator()

    def test_dependency_forward_and_backward_pass(self):
        r=self.engine.plan(project())
        self.assertEqual(r['summary']['duration'],5)
        self.assertEqual(r['baseline']['critical_ids'],['A','B'])
        self.assertEqual(r['tasks'][1]['start'],2)
        self.assertEqual(r['tasks'][1]['finish_date'],'2026-10-16')

    def test_parallel_tasks_with_spare_capacity(self):
        p=project();p['tasks'][1]['dependencies']=[]
        r=self.engine.plan(p)
        self.assertEqual(r['summary']['duration'],3)
        self.assertEqual({t['start'] for t in r['tasks']},{0})

    def test_resource_leveling_eliminates_overload(self):
        p=project();p['tasks']=[task('A',2,3),task('B',3,3)]
        r=self.engine.plan(p)
        self.assertEqual(r['summary']['duration'],5)
        self.assertGreater(r['summary']['baseline_conflict_days'],0)
        assert_invariants(self,r)

    def test_equipment_calendar_wait(self):
        p=project();p['resources'].append({'id':'crane','name':'Crane','kind':'equipment','capacity':1,'rate':200,'unavailable_days':[0,1]})
        p['tasks'][0]['requirements']['crane']=1
        r=self.engine.plan(p)
        self.assertEqual(r['tasks'][0]['start'],2)
        assert_invariants(self,r)

    def test_over_capacity_blocks_descendants(self):
        p=project();p['tasks'][0]['requirements']['crew']=5
        r=self.engine.plan(p)
        self.assertFalse(r['summary']['feasible'])
        self.assertEqual(r['summary']['blocked'],2)
        self.assertIn('Blocked predecessor',r['tasks'][1]['reason'])
        self.assertFalse(r['cost']['complete_estimate'])

    def test_material_waits_for_delivery(self):
        p=project();p['resources'].append({'id':'cement','name':'Cement','kind':'material','stock':5,'rate':2,'deliveries':[{'day':4,'quantity':5}]})
        p['tasks'][0]['requirements']['cement']=10
        r=self.engine.plan(p)
        self.assertEqual(r['tasks'][0]['start'],4)
        assert_invariants(self,r)

    def test_material_reservations_protect_later_activity(self):
        p=project();p['strategy']='priority'
        p['resources'].append({'id':'m','name':'Material','kind':'material','stock':5,'rate':2,'deliveries':[{'day':5,'quantity':5}]})
        p['tasks']=[task('A',1,1),task('B',1,1)]
        p['tasks'][0].update(priority=5,release_day=6,requirements={'m':8})
        p['tasks'][1]['requirements']={'m':3}
        r=self.engine.plan(p)
        self.assertEqual(r['tasks'][0]['start'],6)
        self.assertEqual(r['tasks'][1]['status'],'blocked')
        assert_invariants(self,r)

    def test_material_global_shortfall(self):
        p=project();p['resources'].append({'id':'m','name':'Material','kind':'material','stock':5})
        for t in p['tasks']:t['requirements']['m']=4
        r=self.engine.plan(p)
        self.assertEqual(r['materials'][0]['shortfall'],3)
        self.assertEqual(r['summary']['blocked'],1)

    def test_cycle_rejected(self):
        p=project();p['tasks'][0]['dependencies']=['B']
        with self.assertRaisesRegex(ValidationError,'Circular'):
            self.engine.plan(p)

    def test_invalid_references_and_numbers(self):
        changes=[('missing dependency',lambda p:p['tasks'][0].update(dependencies=['Z'])),
                 ('missing resource',lambda p:p['tasks'][0].update(requirements={'missing':1})),
                 ('negative duration',lambda p:p['tasks'][0].update(duration=-1)),
                 ('nonfinite budget',lambda p:p.update(budget=float('nan'))),
                 ('fractional crew',lambda p:p['tasks'][0].update(requirements={'crew':1.5})),
                 ('duplicate ID',lambda p:p['tasks'][1].update(id='A')),
                 ('bad date',lambda p:p.update(start_date='tomorrow')),
                 ('bad numeric type',lambda p:p['resources'][0].update(capacity=True))]
        for name,change in changes:
            with self.subTest(name=name):
                p=project();change(p)
                with self.assertRaises(ValidationError):self.engine.plan(p)

    def test_cost_math_and_budget(self):
        p=project();p['tasks'][0]['fixed_cost']=50
        r=self.engine.plan(p)
        self.assertEqual(r['cost']['labour'],1000)
        self.assertEqual(r['cost']['overhead'],500)
        self.assertEqual(r['cost']['total'],1550)
        self.assertEqual(r['cost']['variance'],98450)

    def test_day_boundaries_and_material_single_consumption(self):
        p=project();p['resources'].append({'id':'m','name':'Material','kind':'material','stock':1,'rate':20})
        p['tasks'][0]['requirements']['m']=1
        r=self.engine.plan(p)
        self.assertEqual(r['cost']['material'],20)
        self.assertEqual(r['materials'][0]['reserved'],1)
        self.assertEqual(r['tasks'][1]['start'],r['tasks'][0]['finish'])

    def test_release_day_and_priority_selection(self):
        p=project();p['strategy']='priority';p['resources'][0]['capacity']=2
        p['tasks']=[task('A',2,2),task('B',3,2)]
        p['tasks'][1]['priority']=5
        r=self.engine.plan(p)
        self.assertEqual(r['tasks'][1]['start'],0)
        self.assertEqual(r['tasks'][0]['start'],3)

    def test_search_horizon_is_bounded(self):
        p=project();p['tasks'][0].update(release_day=1999,duration=2)
        r=self.engine.plan(p)
        self.assertEqual(r['summary']['blocked'],2)
        self.assertIn('2000 days',r['tasks'][0]['reason'])

    def test_demo_frozen_expectations(self):
        p=json.loads((ROOT/'examples/demo_project.json').read_text())
        r=self.engine.plan(p)
        self.assertTrue(r['summary']['feasible'])
        self.assertEqual(r['summary']['duration'],31)
        self.assertEqual(r['summary']['baseline_duration'],26)
        self.assertEqual(r['cost']['total'],835700)
        assert_invariants(self,r)

    def test_determinism_and_input_immutability(self):
        p=project();before=copy.deepcopy(p)
        self.assertEqual(self.engine.plan(p),self.engine.plan(p))
        self.assertEqual(p,before)

    def test_random_dag_schedule_invariants(self):
        rng=random.Random(203)
        for case in range(40):
            p=project();p['strategy']=rng.choice(['critical','priority','shortest'])
            p['resources'][0].update(capacity=rng.randint(2,8),unavailable_days=[5,12])
            p['resources'].append({'id':'m','name':'Materials','kind':'material','stock':10,'deliveries':[{'day':8,'quantity':100}]})
            p['tasks']=[]
            for i in range(8):
                t=task(str(i),rng.randint(1,4),rng.randint(1,4),[str(j) for j in range(i) if rng.random()<.2])
                t.update(priority=rng.randint(1,5),release_day=rng.randint(0,2))
                t['requirements']['m']=rng.randint(1,8)
                p['tasks'].append(t)
            r=self.engine.plan(p)
            with self.subTest(case=case):assert_invariants(self,r)

    def test_csv_formula_protection(self):
        p=project();p['tasks'][0]['name']='=HYPERLINK("bad")'
        text=ReportExporter().schedule_csv(self.engine.plan(p))
        self.assertIn("'=HYPERLINK",text)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.service=ApplicationService(Path(self.tmp.name)/'db.sqlite3')

    def tearDown(self):self.tmp.cleanup()

    def test_save_plan_history_and_persistence(self):
        status,r=self.service.dispatch('POST','/api/plan',{'project':project()})
        self.assertEqual(status,200)
        meta=r['saved']
        reopened=ProjectRepository(self.service.repository.path)
        self.assertEqual(reopened.get(meta['id'])['project']['name'],'Test site')
        self.assertEqual(len(reopened.history(meta['id'])),1)
        self.assertEqual(reopened.run(meta['run_id'])['summary']['duration'],5)

    def test_stale_save_rejected(self):
        _,r=self.service.dispatch('POST','/api/projects',{'project':project()})
        status,result=self.service.dispatch('POST','/api/projects',{'project':project(),'project_id':r['id'],'revision':0})
        self.assertEqual(status,409)
        self.assertEqual(self.service.repository.get(r['id'])['revision'],1)

    def test_scenario_does_not_save_and_handles_infeasibility(self):
        status,r=self.service.dispatch('POST','/api/scenario',{'project':project(),'resource_id':'crew','amount':-4})
        self.assertEqual(status,200)
        self.assertFalse(r['comparable'])
        self.assertIsNone(r['days_saved'])
        self.assertEqual(self.service.repository.list(),[])

    def test_bad_json_shapes_return_validation_errors(self):
        for payload in ({'project':None},{'project':[]},{'project':{'name':'missing'}}):
            status,_=self.service.dispatch('POST','/api/plan',payload)
            self.assertEqual(status,422)


if __name__=='__main__':unittest.main(verbosity=2)
