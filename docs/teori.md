# PX4 Ekosistemi: Teknik Notlar

**Hazırlayan:** Şevketcan Sezen

## 1. PX4, SITL ve Gazebo nedir?

PX4 bir otopilottur, yani drone'un beynidir. Uçağın sensörlerinden (IMU, GPS, barometre, hava hızı sensörü) gelen verilerle uçağın durumunu belirler ve kendi kararlarını verir. Kararlarını motorlara ve kanatlardaki hareketli parçalara uygular. Yüklenen rotaları uygulayarak drone'u uçurur. Dışarıdan (QGroundControl, Python kodu veya ROS 2 gibi programlardan) yönlendirmeler alır, ama bunları uygun hareket mi diye kontrol ettikten sonra uygular. Gerçek bir drone'da Cube Orange gibi bir uçuş kontrol kartında çalışır.

SITL (Software In The Loop), PX4'ün gerçek bir kart yerine bilgisayarda bir program olarak çalışmasıdır. PX4, SITL sayesinde sanal bir ortamdan veri alabilir.

Gazebo, gerçek dünyadaki gibi veriler üreten bir sanal ortamdır. Uçağın fiziğini hesaplar, gerçeğe benzeyen sensör verilerini PX4'e gönderir ve PX4'ün komutlarını sanal uçağa uygular. Böylece PX4 kendini gerçek bir drone'da sanar ve gerçek donanıma zarar verme riski olmadan test yapılabilir.

## 2. QGroundControl ne işe yarar?

QGroundControl (QGC) bir yer kontrol istasyonudur. Drone'un konumu, irtifası, hızı, uçuş modu, batarya ve GPS durumu gibi bilgileri PX4'ten alarak ekranda gösterir. Rota planlaması yapılarak rotanın PX4'e gönderilmesini sağlar. Ayrıca kalkış, eve dönüş ve mod değiştirme gibi komutlar verebilir ve PX4'ün ayarlarını değiştirebilir. PX4, güvenlik için bir yer istasyonu bağlı olmadan arm izni vermez.

Bu projede rota QGC'de çizilip PX4'e yüklendi ve uçuş QGC'nin haritasından izlendi.

## 3. MAVLink ve MAVSDK nedir?

MAVLink, drone ile yer istasyonu ve diğer programlar arasında kullanılan ortak mesajlaşma dilidir (protokolüdür). Konum, hız, durum bilgileri, komutlar ve görev öğeleri bu dilde mesajlar olarak gönderilir. Örneğin `HEARTBEAT` mesajı "buradayım" anlamına gelir; rota yüklenirken `NAV_TAKEOFF`, `NAV_WAYPOINT` gibi görev öğeleri gönderilir. QGroundControl PX4 ile doğrudan MAVLink ile konuşur.

MAVSDK ise Python gibi programlama dillerinden gelen emirleri MAVLink mesajlarına dönüştürüp PX4'e aktaran bir kütüphanedir. Örneğin Python'da `drone.action.arm()` yazıldığında, MAVSDK bunu gerekli MAVLink mesajına çevirip PX4'e gönderir; mesajları tek tek elle hazırlamaya gerek kalmaz.

Bu projede Python kodu, MAVSDK aracılığıyla UDP 14540 portundan PX4'e bağlandı.

```
QGC ─────────────────────── MAVLink ──▶ PX4
Python ──▶ MAVSDK ───────── MAVLink ──▶ PX4
```

## Kaynaklar

- İHA Masterclass, Enes Durudeniz (Bölüm 6, 7, 8, 9, 12, 14)
- PX4 dokümantasyonu: https://docs.px4.io/main/en/
- MAVSDK dokümantasyonu: https://mavsdk.mavlink.io/
