import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"K2PAi_axxu3H","alg":"RS256","n":"0QMHGhEwkd4VoN7DNUsxVXw6PQWBoIfd_kx1rZ9o-maM7WOE","e":"AQAB","p":"tSBaHg_rdMcmCJsy7xRIqkwqMEAP26W4AhK4wvBOEm0UTS5c","q":"ip_znBTNB8DFWUnMFJuBxOpmMpXVECtJlZT-Zn9JqXBg070i","dp":"nOmc9mh9V543ohnegr6RvX0Lc0MGXD4GSPhjwgyrNOdYWA6X","dq":"vH34Ug0edYU81RqFsFCF36HdQG937ENZB4DsrO_SHaWPjwod"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"K2PAi_axxu3H\",\"alg\":\"RS256\",\"n\":\"0QMHGhEwkd4VoN7DNUsxVXw6PQWBoIfd_kx1rZ9o-maM7WOE\",\"e\":\"AQAB\",\"p\":\"tSBaHg_rdMcmCJsy7xRIqkwqMEAP26W4AhK4wvBOEm0UTS5c\",\"q\":\"ip_znBTNB8DFWUnMFJuBxOpmMpXVECtJlZT-Zn9JqXBg070i\",\"dp\":\"nOmc9mh9V543ohnegr6RvX0Lc0MGXD4GSPhjwgyrNOdYWA6X\",\"dq\":\"vH34Ug0edYU81RqFsFCF36HdQG937ENZB4DsrO_SHaWPjwod\"}";
    JWK.parse(jwk);
  }
}
