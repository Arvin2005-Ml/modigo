import type {MetadataRoute} from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    id: '/', name: 'فانیلو — وقتِ خودت', short_name: 'فانیلو',
    description: 'چند پیشنهاد ساده برای وقت آزاد، با حال و شرایط خودت.',
    lang: 'fa', dir: 'rtl', start_url: '/', scope: '/', display: 'standalone',
    background_color: '#f6f8f7', theme_color: '#f6f8f7',
    categories: ['lifestyle', 'entertainment'],
    icons: [
      {src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any'},
      {src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any'},
      {src: '/icons/maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable'}
    ]
  };
}
