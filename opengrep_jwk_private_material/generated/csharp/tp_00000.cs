using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"FOXCRnDCklTj","alg":"RS256","n":"eKLGgdbD9ZvILURwaRYpyEbmR_9z1kGw_aqNmg9XY3MegIXo","e":"AQAB","d":"ZiwVzH6vVwGeH26xVddimLhkXh2hV-VAGAEWyzX9Bnd19dVq4Ex-Kg0ECI1XJeX2"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"FOXCRnDCklTj\",\"alg\":\"RS256\",\"n\":\"eKLGgdbD9ZvILURwaRYpyEbmR_9z1kGw_aqNmg9XY3MegIXo\",\"e\":\"AQAB\",\"d\":\"ZiwVzH6vVwGeH26xVddimLhkXh2hV-VAGAEWyzX9Bnd19dVq4Ex-Kg0ECI1XJeX2\"}";
    var key = new JsonWebKey(jwk);
  }
}
