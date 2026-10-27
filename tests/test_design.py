import math
import struct
import unittest
import zlib
from design import artwork, layout, settings, frame_box, video_box, FRAMES
from fonts import FONTS, width, wrap


def pixels(png):
    offset,data=8,b''
    while offset<len(png):
        size=struct.unpack('!I',png[offset:offset+4])[0]
        if png[offset+4:offset+8]==b'IDAT':
            data+=png[offset+8:offset+8+size]
        offset+=size+12
    raw=zlib.decompress(data)
    return lambda x,y: tuple(raw[y*(720*4+1)+1+x*4:y*(720*4+1)+5+x*4])


class DesignTests(unittest.TestCase):
    def options(self,**changes):
        data=dict(template='blue',frame_style='none',color='#20375d',title='Tiêu đề',body='Nội dung')
        data.update(changes)
        return settings(data)

    def test_transparent_to_opaque_without_hard_edge(self):
        sample=pixels(artwork(self.options()))
        self.assertEqual(sample(360,500)[3],0)
        self.assertTrue(70<sample(360,680)[3]<210)
        self.assertEqual(sample(360,850)[3],255)
        alphas=[sample(360,y)[3] for y in range(550,800)]
        self.assertEqual(alphas,sorted(alphas))
        self.assertLessEqual(max(b-a for a,b in zip(alphas,alphas[1:])),3)

    def test_frame_motion_independent_of_background_and_text(self):
        first=self.options(frame_style='pink',frame_y=58)
        second=self.options(frame_style='pink',frame_y=70)
        p,q=pixels(artwork(first)),pixels(artwork(second))
        for y in range(550,740,20):
            self.assertEqual(p(360,y),q(360,y))
        self.assertNotEqual(p(360,800),q(360,800))
        self.assertEqual(layout(first),layout(second))

    def test_gradient_colors_and_transparent_frame(self):
        opts=self.options(background='gradient',color='#ff0000',color2='#0000ff',frame_style='minimal',frame_opacity=0)
        sample=pixels(artwork(opts))
        self.assertLess(sample(360,1200)[0],sample(360,850)[0])
        self.assertGreater(sample(360,1200)[2],sample(360,850)[2])
        opts['frame_style']='none'
        self.assertEqual(artwork(opts),artwork(self.options(background='gradient',color='#ff0000',color2='#0000ff',frame_style='minimal',frame_opacity=0)))

    def test_frame_opacity_applies_to_whole_multilayer_frame(self):
        images=[pixels(artwork(self.options(frame_style='pink',frame_opacity=value))) for value in (0,50,100)]
        before,half,full=[image(360,850) for image in images]
        for index in range(3):
            self.assertLessEqual(abs(half[index]-(before[index]+full[index])/2),1)

    def test_bundled_fonts_wrap_wide_and_vietnamese_text(self):
        for font in FONTS:
            text='WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW Áo mới tiếng Việt đẹp'
            lines=wrap(text,font,48,260)
            self.assertTrue(all(width(line,font,48)<=260 for line in lines))
            self.assertEqual(''.join(''.join(lines).split()),''.join(text.split()))
            self.assertEqual(wrap('Dòng một\nDòng hai',font,20,500),['Dòng một','Dòng hai'])

    def test_text_layout_no_cta_and_custom_settings(self):
        opts=self.options(title_font='serif-bold',title_size=42,title_x=35,title_y=20,title_color='#123456',title_align='right',body_font='mono')
        items=layout(opts)
        self.assertEqual([i['key'] for i in items],['title','body'])
        self.assertEqual(items[0]['font'],'serif-bold')
        self.assertEqual(items[0]['size'],42)
        self.assertEqual(items[0]['y'],256)
        self.assertEqual(items[0]['color'],'#123456')
        with self.assertRaises(ValueError):
            layout(self.options(title_y=98,title_size=72))

    def test_frame_stays_in_canvas_at_extremes(self):
        for x in (0,100):
            for y in (0,95):
                b=frame_box(self.options(frame_x=x,frame_y=y,frame_width=100,frame_height=60))
                self.assertGreaterEqual(b['x'],0)
                self.assertLessEqual(b['x']+b['width'],720)
                self.assertLessEqual(b['y']+b['height'],1280)

    def test_pixel_coordinates_and_ninety_pixel_text(self):
        opts=self.options(units='px',title='THỬ',title_size=90,title_x=90,title_y=90,title_width=500,
                          frame_x=24,frame_y=800,frame_width=672,frame_height=350,
                          video_x=-90,video_y=120,video_width=540,video_height=960)
        item=layout(opts)[0]
        self.assertEqual((item['x'],item['y'],item['size']),(90,90,90))
        self.assertEqual(frame_box(opts),dict(x=24,y=800,width=672,height=350))
        self.assertEqual(video_box(opts),dict(x=-90,y=120,width=540,height=960))
        with self.assertRaises(ValueError):layout(self.options(units='px',title_x=700,title_width=100))

    def test_untrusted_values_rejected(self):
        for value in (-1,101,True,'50',math.inf,math.nan):
            with self.assertRaises(ValueError):self.options(opacity=value)
        for opts in [dict(title_font='../secret'),dict(color='#fff;movie=x'),dict(frame_style='custom',frame_id='../x')]:
            with self.assertRaises(ValueError):self.options(**opts)


if __name__=='__main__':unittest.main()
