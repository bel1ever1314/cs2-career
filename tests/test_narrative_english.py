"""Authored prose, optional locale fields and Major ceremony regressions."""
from copy import deepcopy
import re
from unittest import TestCase
from unittest.mock import patch

from cs2career.career import Career, arcs, plot, retirement, story
from cs2career.career.localization import catalog, enrich, phrases, present, translate
from cs2career.career.notifications import reconcile
from cs2career.league import Season


class NarrativeCatalogTests(TestCase):
    def english(self, text):
        self.assertTrue(text)
        self.assertIsNone(re.search(r'[\u4e00-\u9fff]', text), text)

    def test_all_builtin_chapters_choices_endings_and_injuries_have_english(self):
        cfg = arcs.base_config()
        for name, node in cfg['chapters'].items():
            with self.subTest(chapter=name):
                self.english(node['title_en'])
                self.assertEqual(len(node['text']), len(node['text_en']))
                for zh, en in zip(node['text'], node['text_en']):
                    self.english(en)
                    self.assertEqual(set(re.findall(r'\{\w+\}',zh)),set(re.findall(r'\{\w+\}',en)))
                for choice in node['choices']: self.english(choice['label_en'])
        for node in [*cfg['endings'].values(), *retirement.config()['endings'].values()]:
            self.english(node['title_en']); self.english(node['text_en'])
        for injury in cfg['injuries']:
            self.english(injury['name_en'])
            self.assertEqual(len(injury['texts']),len(injury['texts_en']))
            for text in injury['texts_en']:self.english(text)
        for kind in ('wish','train'):
            self.assertEqual(len(cfg['birthday'][kind]),len(cfg['birthday'][kind+'_en']))
            for text in cfg['birthday'][kind+'_en']:self.english(text)

    def test_opening_milestone_stories_render_both_languages(self):
        for node in story.load_stories():
            ctx={key:'Sample' for key in re.findall(r'\{(\w+)\}',node['text']+node['title'])}
            result=story.render(node,ctx)
            self.english(result['title_en']);self.english(result['text_en'])
            self.assertNotIn('{',result['text_en'])
            self.assertEqual(node['id'],result['id'])

    def test_source_edits_do_not_silently_reuse_unrelated_english(self):
        raw=deepcopy(catalog()[0]['career_arcs'])
        raw['chapters']['ordinary_intro']['text']=['玩家自己重写的正文']
        raw['chapters']['ordinary_intro']['choices'][0]['label']='新选项'
        out=enrich('career_arcs',raw)['chapters']['ordinary_intro']
        self.assertNotIn('text_en',out)
        self.assertNotIn('label_en',out['choices'][0])
        custom=dict(id='pack-story',title='自定义标题',text='自定义正文',text_en='Custom prose.')
        self.assertEqual(custom,present(custom))

    def test_old_records_are_presented_without_mutating_saved_choices_or_rewards(self):
        raw=dict(id='old',title='选择之后',text='你和她约好训练时专心、见面时也专心。这不是把感情放在职业的对立面，而是努力让两件重要的事都走得更长。',
                 choices=[dict(id='ok',label='继续（属性点+2）',reward=2,action='continue')])
        saved=deepcopy(raw);out=present(raw)
        self.english(out['title_en']);self.english(out['text_en']);self.english(out['choices'][0]['label_en'])
        self.assertEqual(saved,raw)
        self.assertEqual(2,out['choices'][0]['reward'])
        self.assertEqual('ok',out['choices'][0]['id'])

    def test_builtin_live_incidents_and_letters(self):
        rows=[plot.birthday_popup('TestPlayer'),plot.coach_popup('Sample Major'),plot.whisper_popup(),
              plot.probe_popup(),plot.ban_popup('TestPlayer',80),plot.loan_default_popup(),plot.loan_flee_news('TestPlayer',80),
              plot.whisper_letter('TestPlayer'),plot.ban_letter('TestPlayer'),plot.loan_flee_ban_letter('TestPlayer'),
              plot.loan_release_letter('TestPlayer','Sample Team',True),plot.loan_release_letter('TestPlayer','Sample Team',False)]
        for raw in rows:
            out=present(raw)
            with self.subTest(title=raw['title']):
                self.english(out['title_en']);self.english(out.get('text_en') or out.get('body_en'))
                for choice in out.get('choices',[]):self.english(choice['label_en'])

    def test_injury_effects_and_old_birthday_reactions_are_translated(self):
        cfg=arcs.base_config()
        for item in cfg['injuries']:
            for paragraph in item['texts']:
                text=paragraph+'\n\n游戏效果：火力 70→69，狙击 80→79。状态暂时-3，到2026-04-12解除。\n这是生涯世界的伤病设定，不代表现实诊断。\n她告诉你：‘今天不需要再逞强，我陪你把这段时间过完。’'
                out=translate(text);self.english(out)
                self.assertIn('70→69',out);self.assertIn('2026-04-12',out)
        for kind in ('wish','train'):
            for text in cfg['birthday'][kind]:
                self.english(translate(arcs.render(text,dict(teammate='TestPlayer',player='Tester'))))


class NarrativeBusinessTests(TestCase):
    def setUp(self):
        self.s=Season(2026,'2026');self.c=Career();self.s.career=self.c
        save=patch.object(self.c,'save');save.start();self.addCleanup(save.stop)
        self.c.create(dict(mode='create',era='2026',name='Tester',org='Test Club',
                           origin='academy',role='rifle',region='EU'),self.s)
        self.c.story_queue=[];self.c.inbox=[];self.s.events=[]
        self.c.incident_state['story_timing']={'windows':[dict(key='fixture',start='2020-01-01',until='2099-12-31',event='Fixture')],'deferred':[]}

    def test_generated_press_context_and_focus_reward(self):
        v=arcs.state(self.c);v.update(romance='stable',partner='ordinary')
        arcs.opinion(self.c,self.s,'最近30图平均Rating约0.82。持续低迷的数据让外界开始质疑这个位置，要求更换选手的声音越来越多。','locale-test')
        row=next(r for r in self.c.story_queue if r.get('arc')=='press')
        self.assertNotRegex(row['text_en'],r'[\u4e00-\u9fff{}]')
        self.assertIn('0.82',row['text_en'])
        before=self.c.attr_points
        choice=next(x for x in row['choices'] if x['id']=='endure')
        self.c.ack_story(row['id'],'endure',self.s)
        self.c.ack_story(row['id'],'endure',self.s)
        self.assertEqual(before+choice['reward'],self.c.attr_points)
        history=arcs.state(self.c)['history'][-1]
        self.assertEqual(row['text_en'],history['text_en'])

    def test_all_na_family_outcomes_have_english_mail(self):
        for titles,passed,rating in (([],False,None),([],True,1.15),([dict(name='Sample Cup')],False,.9)):
            with self.subTest(titles=bool(titles),passed=passed):
                self.c.inbox=[];self.c.story_queue=[];self.c.incident_state['news_publications']=[]
                v=arcs.state(self.c);v['deadline']='2027-01-01'
                with patch.object(arcs,'na_achievements',return_value=titles):
                    arcs.na_first_assessment(self.c,self.s,dict(maps=30,rating=rating,passed=passed))
                mail=self.c.inbox[0]
                self.assertNotRegex(mail['body_en'],r'[\u4e00-\u9fff{}]')
                self.assertEqual('invite_wait' if titles or passed else 'return_pending',v['na'])

    def test_major_award_ceremony_survives_both_modes_and_ack_is_idempotent(self):
        mine=self.c.my_team(self.s.teams)
        for quick in (False,True):
            with self.subTest(quick=quick):
                self.c.assist['quick_mode']=quick;self.c.story_queue=[]
                ev=dict(id='major-'+str(quick),name='Sample Major',type='major',status='done',
                        champion='Other',dates=[self.s.date],prize=0,matches=[dict(id='m',played=True,
                        team_a=mine['name'],team_b='Other',winner='Other',stage='GF',maps=[])],
                        awards=dict(mvp=dict(player='Winner',team='Other'),evp=[dict(player='Runner',team=mine['name'])],
                                    five=[dict(player='Role'+str(i),role=role,team='Other') for i,role in enumerate(('igl','awp','entry','lurk','rifle'))]))
                self.s.events=[ev]
                with patch.object(self.c,'watch'),patch.object(self.c,'_event_in_current_stint',return_value=True):
                    self.c.award_event(self.s,ev)
                    before=self.c.attr_points
                    reconcile(self.c,self.s)
                    row=next(r for r in self.c.story_queue if r.get('kind')=='awards')
                    self.assertEqual('major',row['class']);self.assertEqual(5,len(row['five']))
                    self.assertTrue(row['mvp']);self.assertTrue(row['evp'])
                    self.c.ack_story(row['id'],'',self.s);self.c.ack_story(row['id'],'',self.s)
                    self.c.award_event(self.s,ev)
                    self.assertEqual(before,self.c.attr_points)
                    self.assertFalse(any(r.get('kind')=='awards' for r in self.c.story_queue))
                self.c.story_queue=[dict(id='t1-'+str(quick),kind='awards',**{'class':'t1'},title='Other cup')]
                reconcile(self.c,self.s)
                self.assertFalse(self.c.story_queue)
