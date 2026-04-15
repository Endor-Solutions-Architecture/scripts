using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"VyH1NMaoBSjQ","alg":"RS256","n":"Bx8OkR2eUQVldpN4y2yhBKfRMg3Sy_km2dP4V4s9xwrzKhyv","e":"AQAB","d":"E7XK6fH7"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"VyH1NMaoBSjQ\",\"alg\":\"RS256\",\"n\":\"Bx8OkR2eUQVldpN4y2yhBKfRMg3Sy_km2dP4V4s9xwrzKhyv\",\"e\":\"AQAB\",\"d\":\"E7XK6fH7\"}";
    var key = new JsonWebKey(jwk);
  }
}
