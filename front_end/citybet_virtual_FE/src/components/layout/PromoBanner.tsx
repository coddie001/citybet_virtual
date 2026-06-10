import bannerImg from '../../assets/banner1.jpg'

export function PromoBanner() {
  return (
    <section className="overflow-hidden rounded-2xl">
      <img
        src={bannerImg}
        alt="CityBet Virtuals promotion"
        className="h-auto w-full object-cover"
        style={{ maxHeight: 'clamp(180px, 22vw, 420px)' }}
      />
    </section>
  )
}
