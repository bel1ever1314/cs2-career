"""Monthly digest structure, quiet quick mode and narrative localisation."""
import json
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from cs2career.career import arcs, news
from cs2career.career.mail import new_mail
from cs2career.paths import data_file


class _Career:
    exists=True
    def __init__(self,quick=False):
        self.incident_state={};self.inbox=[];self.story_queue=[]
        self.assist={'quick_mode':quick}
    def over(self):return False
    def _push_mail(self,kind,date,payload,extra):
        row=new_mail(kind,date,payload,extra);self.inbox.append(row);return row


class MonthlyDigestTests(TestCase):
    def fixture(self,quick=False):
        c=_Career(quick)
        teams=[dict(id='a',name='天禄',players=[dict(player_id='one',name='someone')]),
               dict(id='b',name='LVG',players=[])]
        table=lambda teams,day:[dict(id=t['id'],name=t['name'],rank=i) for i,t in enumerate(teams,1)]
        s=SimpleNamespace(date='2026-01-03',year=2026,teams=teams,events=[],vrs=SimpleNamespace(table=table))
        news.initialize(c,s)
        return c,s

    def test_quick_monthly_archived_bilingual_without_popup(self):
        c,s=self.fixture(True)
        c.incident_state['arcs']={'series':[dict(date='2026-01-18',win=True,maps=[{'rating':1.3}])]}
        s.date='2026-01-20'
        event=dict(id='cup',name='Recorded Cup',champion='天禄',type='t2',awards={'mvp':{'player':'someone'}})
        news.event_done(c,s,event);news.event_done(c,s,event)
        s.teams[1]['players']=s.teams[0]['players'];s.teams[0]['players']=[]
        news.capture_roster(c,s)
        s.date='2026-02-01';news.tick(c,s);news.tick(c,s)
        self.assertEqual([],c.inbox);self.assertEqual([],c.story_queue)
        history=c.incident_state['arcs']['history']
        self.assertEqual(1,len(history))
        row=history[0]
        self.assertEqual('monthly:2026-01',row['publication_key'])
        self.assertEqual(['team','champions','transfers','ranking'],[x['id'] for x in row['sections']])
        self.assertIn('MVP: someone.',row['text_en'])
        self.assertIn('someone joined LVG from 天禄.',row['text_en'])
        self.assertIn('1 series · 1 wins, 0 losses',row['text_en'])
        self.assertIn('Monthly review',row['title_en'])

    def test_normal_monthly_has_one_readable_summary_without_empty_sections(self):
        c,s=self.fixture()
        s.date='2026-02-02';news.tick(c,s)
        self.assertEqual(1,len(c.story_queue))
        self.assertEqual(['ranking'],[x['id'] for x in c.inbox[0]['sections']])
        self.assertNotIn('没有官宣',c.inbox[0]['body'])
        self.assertNotIn('【转会',c.inbox[0]['body'])
        self.assertLess(len(c.inbox[0]['body']),250)

    def test_month_jump_does_not_backdate_current_ranking(self):
        c,s=self.fixture(True)
        s.date='2026-03-01';news.tick(c,s)
        history=c.incident_state['arcs']['history']
        self.assertEqual(2,len(history));self.assertEqual([],c.inbox)
        self.assertEqual([],history[0]['sections'])
        self.assertEqual(['ranking'],[x['id'] for x in history[1]['sections']])

    def test_older_fact_can_translate_without_guessing_unknown_content(self):
        fact=news._fact_item({'text':'ZywOo 从 Vitality 转入 天禄。'})
        self.assertEqual('ZywOo joined 天禄 from Vitality.',fact['text_en'])
        unknown=news._fact_item({'text':'扩展包作者自己写的内容'})
        self.assertEqual(unknown['text'],unknown['text_en'])


class NarrativeCopyTests(TestCase):
    def test_final_decision_carries_english_without_changing_choices(self):
        from cs2career.league.tournament_auto import moment
        c=_Career();c.team_id='mine';c.player_name='Player'
        s=SimpleNamespace(year=2026,career=c,your_team_name=lambda:'Vitality')
        event=dict(id='major',name='Major')
        match=dict(id='final',stage='GF',team_a='Vitality',team_b='天禄')
        moment(c,s,event,match,'final')
        row=c.story_queue[0]
        self.assertEqual('One match from the trophy',row['title_en'])
        self.assertIn('The opponent is 天禄.',row['text_en'])
        self.assertEqual(['manual','simulate','later'],[choice['id'] for choice in row['choices']])
        self.assertTrue(all(choice.get('label_en') for choice in row['choices']))

    def test_eighteen_branches_keep_ids_but_do_not_narrate_the_forecast(self):
        data=json.loads(data_file('major_exit_stories.json').read_text('utf-8'))['stories']
        self.assertEqual(18,len(data))
        for key,row in data.items():
            with self.subTest(key=key):
                content=' '.join([row['title'],row['title_en'],*row['text'],*row['text_en']])
                self.assertNotIn('{expected}',content)
                self.assertNotIn('赛前',content)
                self.assertNotIn('pre-event',content)
                self.assertNotIn('预测',content)
                self.assertGreater(len(row['text'][0]),180)

    def test_major_news_removes_explicit_algorithm_and_has_english(self):
        data=json.loads(data_file('career_news.json').read_text('utf-8'))
        for key in ('champion_favourite','champion_surprise','major_disappointed','major_expected','major_excited'):
            with self.subTest(key=key):
                row=data[key];content=json.dumps(row,ensure_ascii=False)
                self.assertNotIn('{expected}',content);self.assertNotIn('{rank}',content)
                self.assertNotIn('赛前',content);self.assertNotIn('预测',content)
                self.assertGreater(len(row['text'][0]),400)
                self.assertGreater(len(row['text_en'][0]),500)

    def test_chinese_only_override_does_not_retain_stale_english(self):
        class Registry:
            def payloads(self,kind):
                return [{'arc_overrides':{
                    'reports':{'monthly':{'title':'自定义月报','text':['自己的内容']}},
                    'chapters':{'romance_start':{'title':'自定义章节','text':['自己的章节'],
                        'choices':[{'id':'none','label':'新的中文选项'}]}}
                }}]
        cfg=arcs._config(Registry())
        self.assertNotIn('title_en',cfg['reports']['monthly'])
        self.assertNotIn('text_en',cfg['reports']['monthly'])
        chapter=cfg['chapters']['romance_start']
        self.assertNotIn('text_en',chapter)
        option=next(r for r in chapter['choices'] if r['id']=='none')
        self.assertNotIn('label_en',option)
        with patch.object(arcs,'config',return_value=cfg):
            self.assertEqual(('自定义月报','自己的内容'),news.report(None,'monthly','same',{},language='en'))

    def test_english_report_resolves_corresponding_context(self):
        context=dict(month='2026-02',headline='中文头条',headline_en='English headline',
                     summary='中文摘要',summary_en='English summary',sections='中文正文',sections_en='English body')
        title,body=news.report(None,'monthly','2026-02',context,language='en')
        self.assertIn('English headline',title)
        self.assertEqual('English summary\n\nEnglish body',body)
